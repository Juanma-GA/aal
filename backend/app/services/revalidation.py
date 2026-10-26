"""Revalidating every article (E13): the AR rules over each live article
with today's definitions and reference tables, in the background.

A finding is kept on the article when it is saved (articles.recheck); a
change to a reference table or to a field definition can make it stale --
a code deactivated, a field that became Obligatorio. So:

- `request(db, reason, detail, user_id)` queues a run (in the caller's
  transaction; one already queued is reused: it reads the state when it
  starts) and `schedule(run_id)` starts it once committed. The admin's
  button (reason "manual"), an import or edit of a reference table the
  articles use ("reference_table") and an edit of a field definition
  ("field_definition") do it.
- `run(run_id)` goes through the articles in batches, each in its own
  transaction (an article being saved meanwhile waits for its batch, never
  the other way round), and writes findings and finding_codes -- not the
  version: the data did not change, nobody's edit becomes a 409. The report
  says, by rule, how many findings appeared and how many disappeared.
- A run "queued" or "running" for longer than
  articles.revalidation_stale_minutes (a restart killed it) is marked
  failed when read (`reap_if_stale`).
"""

import asyncio
import logging
import uuid
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import new_error_ref
from app.db.base import async_session_factory
from app.models import Article, ArticleRevalidation
from app.services import audit
from app.services.article_fields import field_defs
from app.services.articles import Checker, data_of, life_of
from app.services.parameters import get_parameter
from app.validacion.articulos import RULES

logger = logging.getLogger(__name__)

BATCH = 500
# The tasks started here (asyncio keeps only a weak reference to them).
_TASKS: set[asyncio.Task] = set()


def _key(finding: dict[str, Any]) -> tuple[str, str, str, str]:
    return finding["code"], finding["field"], finding["problem"], str(finding.get("params", {}).get("position", ""))


async def tables_used(db: AsyncSession) -> set[str]:
    """The reference tables the AR rules read (the fields' and D114)."""
    return {d.table for d in (await field_defs(db)).values() if d.table} | {"D114"}


async def request(db: AsyncSession, reason: str, detail: dict[str, Any], user_id: uuid.UUID | None) -> ArticleRevalidation:
    # Locked until the caller commits: the task that starts it waits for
    # this change, so it reads it (otherwise a new run is queued).
    queued = (
        await db.execute(
            select(ArticleRevalidation).where(ArticleRevalidation.status == "queued").order_by(ArticleRevalidation.created_at).limit(1)
            .with_for_update(skip_locked=True)
        )
    ).scalar_one_or_none()
    if queued is not None:
        # Every change that asked for it, in its detail.
        queued.detail = {**queued.detail, "also": [*queued.detail.get("also", []), {"reason": reason, **detail}]}
        return queued
    found = ArticleRevalidation(id=uuid.uuid4(), reason=reason, detail=detail, status="queued", created_by=user_id)
    db.add(found)
    await db.flush()
    return found


async def after_table_change(db: AsyncSession, table: str, user_id: uuid.UUID | None) -> uuid.UUID | None:
    """Queues a run when the articles read `table`; the caller commits and
    then `schedule`s the id it returns (None: nothing to do)."""
    if table not in await tables_used(db):
        return None
    return (await request(db, "reference_table", {"table": table}, user_id)).id


def schedule(run_id: uuid.UUID) -> None:
    task = asyncio.get_running_loop().create_task(run(run_id))
    _TASKS.add(task)
    task.add_done_callback(_TASKS.discard)


async def drain() -> None:
    """Waits for the runs started here (tests, scripts)."""
    while _TASKS:
        await asyncio.gather(*list(_TASKS), return_exceptions=True)


async def run(run_id: uuid.UUID) -> None:
    async with async_session_factory() as db:
        started = await db.execute(
            update(ArticleRevalidation)
            .where(ArticleRevalidation.id == run_id, ArticleRevalidation.status == "queued")
            .values(status="running")
            .returning(ArticleRevalidation.id)
        )
        await db.commit()
        if started.first() is None:
            return  # another task took it, or it was reaped
        try:
            report = await _revalidate(db)
            outcome: dict[str, Any] = {"status": "done", "report": report}
        except Exception:
            await db.rollback()
            ref = new_error_ref()
            logger.exception("ref=%s article revalidation %s failed", ref, run_id, extra={"ref": ref})
            outcome = {"status": "failed", "error_code": "revalidation_failed", "report": {"error_params": {"ref": ref}}}
        found = await db.get(ArticleRevalidation, run_id)
        if found is None or found.status != "running":
            return  # reaped meanwhile: it stays failed, as the person was told
        for name, value in outcome.items():
            setattr(found, name, value)
        found.finished_at = datetime.now(UTC)
        audit.record(
            db, action="articles.revalidated", entity_type="article_revalidation", entity_id=str(run_id), user_id=found.created_by,
            after={"reason": found.reason, "detail": found.detail, "status": found.status, "report": found.report},
        )
        await db.commit()


async def _revalidate(db: AsyncSession) -> dict[str, Any]:
    checker = await Checker.load(db)
    appeared: Counter[str] = Counter()
    disappeared: Counter[str] = Counter()
    now: Counter[str] = Counter()
    articles = changed = 0
    last: uuid.UUID | None = None
    while True:
        query = select(Article).where(Article.deleted_at.is_(None)).order_by(Article.id).limit(BATCH).with_for_update(of=Article)
        if last is not None:
            query = query.where(Article.id > last)
        batch = (await db.execute(query)).scalars().all()
        if not batch:
            break
        for article in batch:
            before = Counter(_key(f) for f in article.findings or [])
            found = checker.findings(data_of(article), life_of(article))
            if found != article.findings:
                # Not through the ORM: updated_at stays (the data did not change).
                await db.execute(
                    update(Article)
                    .where(Article.id == article.id)
                    .values(findings=found, finding_codes=sorted({f["code"] for f in found}), updated_at=Article.updated_at)
                )
            after = Counter(_key(f) for f in found)
            for key, n in (after - before).items():
                appeared[key[0]] += n
            for key, n in (before - after).items():
                disappeared[key[0]] += n
            for f in found:
                now[f["code"]] += 1
            changed += before != after
        articles += len(batch)
        last = batch[-1].id
        await db.commit()
    rules = [code for code, rule in RULES.items() if rule.severity != "autocorreccion"]
    return {
        "articles": articles,
        "changed": changed,
        "by_rule": {code: {"appeared": appeared[code], "disappeared": disappeared[code], "now": now[code]} for code in rules},
    }


async def reap_if_stale(db: AsyncSession, found: ArticleRevalidation) -> ArticleRevalidation:
    if found.status not in ("queued", "running"):
        return found
    minutes = (await get_parameter(db, "articles"))["revalidation_stale_minutes"]
    if datetime.now(UTC) - found.created_at > timedelta(minutes=minutes):
        found.status, found.error_code, found.finished_at = "failed", "revalidation_interrupted", datetime.now(UTC)
        await db.commit()
        await db.refresh(found)
    return found
