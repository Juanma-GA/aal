"""Validating a CUF against NT 10/17 (E16, RF-03).

- The rules' configuration (`validation_rule`): `settings()`, its hash
  (`rules_hash`: a run made with another configuration is "desactualizado")
  and each rule's effective severity (inactive = "desactivada").
- `context()`: the CUF's whole snapshot for the engine -- the CONFUNFIS
  (confunfis.snapshot_context), its functional products, the parts of its
  articles (with every breakdown, for the cycles), the active codes of the
  products' tables and the AR findings of the articles of its rows and of
  their parts (as kept on each article: E12/E13 recheck them on every save
  and in the revalidation).
- `fingerprint()`: what a run saw (every record it read, by id and version,
  and the CUF's configuration). A later change makes the run
  "desactualizado"; the rows' findings stay fresh meanwhile, refreshed after
  every edit (confunfis.refresh_observations): the incremental validation.
- `validate()`: refreshes the kept findings, runs the engine, gives each
  finding the severity of its rule now and its readable location, marks the
  accepted warnings and stores the run (audited).
- `accept()`: a warning accepted with its justification (never a blocking
  one: that is corrected, or its rule's severity changed by the admin).
- `delivery_problems()`: why "Exportar para entrega" is refused (no run, a
  run with blocking findings, a run out of date) and the extension point
  DELIVERY_GUARDS (E17: a reviewed baseline).
"""

import hashlib
import json
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.texts import text
from app.models import (
    Article,
    ArticlePart,
    ArticleReference,
    FindingAcceptance,
    FunctionalProduct,
    Material,
    PhysicalPosition,
    User,
    ValidationFinding,
    ValidationRule,
    ValidationRun,
)
from app.services import audit, confunfis, cuf
from app.services import confunfis_extras as extras
from app.services.confunfis_graph import key_text
from app.services.reference import codes_by_state
from app.validacion import engine
from app.validacion.catalog import ARTICLE, BLOCKING, BY_CODE, CUF, EXTRA, INCOMPATIBILITY, OFF, PART, PRODUCT, ROW, WARNING

# E17: a reviewed baseline before the delivery. Each guard returns its problems ({"code", "params"}).
DeliveryGuard = Callable[[AsyncSession, Material], Awaitable[list[dict[str, Any]]]]
DELIVERY_GUARDS: list[DeliveryGuard] = []


# ── the rules' configuration ─────────────────────────────────────────────


async def settings(db: AsyncSession) -> dict[str, ValidationRule]:
    return {r.code: r for r in (await db.execute(select(ValidationRule))).scalars()}


def severity_of(rule: ValidationRule | None, code: str) -> str:
    if rule is None:
        return BY_CODE[code].severity
    return rule.severity if rule.active else OFF


def rules_hash(rules: dict[str, ValidationRule]) -> str:
    data = sorted((r.code, r.active, r.severity, json.dumps(r.params, sort_keys=True)) for r in rules.values())
    return hashlib.sha256(repr(data).encode()).hexdigest()


# ── the snapshot ─────────────────────────────────────────────────────────


async def product_codes(db: AsyncSession) -> dict[str, set[str]]:
    return {table: {code for code, active in (await codes_by_state(db, table)).items() if active} for table in extras.PRODUCT_TABLES}


async def context(db: AsyncSession, material: Material) -> engine.Context:
    ctx = await confunfis.snapshot_context(db, material)
    ctx.products = list((await db.execute(
        select(FunctionalProduct).where(FunctionalProduct.material_id == material.id, FunctionalProduct.deleted_at.is_(None))
    )).scalars())
    every = list((await db.execute(select(ArticlePart).where(ArticlePart.deleted_at.is_(None)))).scalars())
    for p in every:
        if p.part_article_id:
            ctx.part_edges.setdefault(p.parent_article_id, set()).add(p.part_article_id)
    ctx.parts = [p for p in every if p.parent_article_id in ctx.cuf_articles]
    ctx.codes = await product_codes(db)
    ids = set(ctx.cuf_articles) | {p.part_article_id for p in ctx.parts if p.part_article_id}
    missing = ids - set(ctx.articles)
    if missing:
        ctx.articles.update({a.id: a for a in (await db.execute(select(Article).where(Article.id.in_(missing)))).scalars()})
    ctx.article_findings = {a: list(ctx.articles[a].findings or []) for a in ids if a in ctx.articles}
    return ctx


async def fingerprint(db: AsyncSession, material: Material) -> str:
    """Every record a validation reads, by id and version, and the CUF's configuration."""
    parts: list[Any] = [("catalog", str(material.catalog_version_id)), ("subcategories", tuple(sorted(await cuf.subcategory_codes(db, material.id))))]
    for model in (PhysicalPosition, FunctionalProduct, extras.ExtraFunction, extras.Incompatibility):
        parts += sorted((str(i), v) for i, v in (await db.execute(select(model.id, model.version).where(model.material_id == material.id, model.deleted_at.is_(None)))).all())
    used = select(PhysicalPosition.article_id).where(PhysicalPosition.material_id == material.id, PhysicalPosition.deleted_at.is_(None))
    parts += sorted((str(i), v) for i, v in (await db.execute(select(Article.id, Article.version).where(Article.id.in_(used)))).all())
    parts += sorted((str(i), v) for i, v in (await db.execute(
        select(ArticlePart.id, ArticlePart.version).where(ArticlePart.parent_article_id.in_(used), ArticlePart.deleted_at.is_(None))
    )).all())
    parts += sorted((str(i), v) for i, v in (await db.execute(
        select(ArticleReference.id, ArticleReference.version).where(ArticleReference.article_id.in_(used), ArticleReference.deleted_at.is_(None))
    )).all())
    # What changes without a version: the AR findings of the articles (and of their parts' articles; a
    # revalidation, E13) and the codes the products are checked against.
    of_parts = select(ArticlePart.part_article_id).where(ArticlePart.parent_article_id.in_(used), ArticlePart.deleted_at.is_(None))
    parts += sorted((str(i), tuple(c or ())) for i, c in (await db.execute(
        select(Article.id, Article.finding_codes).where(Article.id.in_(used) | Article.id.in_(of_parts))
    )).all())
    parts += sorted((table, tuple(sorted(codes))) for table, codes in (await product_codes(db)).items())
    return hashlib.sha256(repr(parts).encode()).hexdigest()


# ── the run ──────────────────────────────────────────────────────────────


def _row_label(r: Any) -> str:
    return f"{key_text((r.sns, r.co, r.al))} · {r.article_name or ''}".rstrip(" ·")


def locate(f: engine.Finding, ctx: engine.Context, material: Material, ordinal: dict[str, int]) -> str:
    """Where a finding is, in words a person finds it by ("fila 23 · A24110 01 00 · FILTRO DE AIRE")."""
    row = ctx.by_id.get(f.row_id) if f.row_id else None
    if f.entity_type == ROW and row is not None:
        return text("validation.location.row", n=ordinal[str(row.id)], row=_row_label(row))
    if f.entity_type == CUF:
        return material.name
    if f.entity_type == ARTICLE:
        article = ctx.articles.get(uuid.UUID(f.entity_id)) if f.entity_id else None
        name = getattr(article, "nombre", "") or ""
        noc = getattr(article, "noc", None)
        return text("validation.location.article", article=f"{noc + ' · ' if noc else ''}{name}")
    if f.entity_type == PART:
        part = next((p for p in ctx.parts if str(p.id) == f.entity_id), None)
        parent = ctx.articles.get(part.parent_article_id) if part is not None else None
        return text("validation.location.part", cop=part.cop, alp=part.alp, parent=getattr(parent, "nombre", "")) if part is not None else f.entity_id
    if f.entity_type == PRODUCT:
        product = next((p for p in ctx.products if str(p.id) == f.entity_id), None)
        return text("validation.location.product", pol=product.pol_code or "—", name=product.designation) if product is not None else f.entity_id
    if f.entity_type == EXTRA and row is not None:
        return text("validation.location.extra", n=ordinal[str(row.id)], row=_row_label(row), sns=f.params.get("sns", ""))
    if f.entity_type == INCOMPATIBILITY:
        item = next((i for i in ctx.incompatibilities if str(i.id) == f.entity_id), None)
        if item is not None:
            a, b = ctx.by_id.get(str(item.row_a_id)), ctx.by_id.get(str(item.row_b_id))
            return f"{_row_label(a) if a else '—'} {item.kind} {_row_label(b) if b else '—'}"
    return f.entity_id


# The value found, by problem: the first parameter that names it.
_FOUND = ("sns", "cs", "co", "al", "qty", "qtys", "ncage", "pn", "pol", "nae", "unit", "cop", "alp", "quantity", "positions", "values", "value")


def _found(f: engine.Finding) -> str | None:
    return next((str(f.params[k]) for k in _FOUND if k in f.params and f.params[k] not in (None, "")), None)


async def _acceptances(db: AsyncSession, material: Material) -> dict[tuple, FindingAcceptance]:
    rows = (await db.execute(select(FindingAcceptance).where(FindingAcceptance.material_id == material.id, FindingAcceptance.deleted_at.is_(None)))).scalars()
    return {(a.rule_code, a.entity_type, a.entity_id, a.problem): a for a in rows}


async def refresh(db: AsyncSession, material: Material) -> None:
    """The findings kept on the rows, products and parts, recomputed."""
    await extras.refresh_products(db, material)
    await confunfis.refresh_observations(db, material)


async def validate(db: AsyncSession, material: Material, user: User | None, trigger: str = "manual", ip: str | None = None) -> ValidationRun:
    started = time.perf_counter()
    await refresh(db, material)
    rules = await settings(db)
    ctx = await context(db, material)
    found = engine.run(ctx, {code: r.params for code, r in rules.items()})
    accepted = await _acceptances(db, material)
    order = sorted(ctx.rows, key=lambda r: (r.sns, r.co, r.al, r.cs_sns or "", r.cs_co or "", r.cs_al or ""))
    ordinal = {str(r.id): n for n, r in enumerate(order, start=1)}
    run = ValidationRun(
        id=uuid.uuid4(), material_id=material.id, user_id=user.id if user else None, trigger=trigger,
        rules_hash=rules_hash(rules), data_fingerprint=await fingerprint(db, material),
    )
    db.add(run)
    await db.flush()
    counts = {"blocking": 0, "warnings": 0, "accepted": 0}
    for f in found:
        severity = severity_of(rules.get(f.code), f.code)
        if severity == OFF:
            continue
        acceptance = accepted.get((f.code, f.entity_type, f.entity_id, f.problem)) if severity == WARNING else None
        db.add(ValidationFinding(
            id=uuid.uuid4(), run_id=run.id, rule_code=f.code, severity=severity, scope=BY_CODE[f.code].scope, entity_type=f.entity_type,
            entity_id=f.entity_id, problem=f.problem, params=f.params, field=f.field, row_id=f.row_id, location=locate(f, ctx, material, ordinal),
            found=_found(f), acceptance_id=acceptance.id if acceptance else None,
        ))
        counts["blocking" if severity == BLOCKING else "accepted" if acceptance else "warnings"] += 1
    run.blocking, run.warnings, run.accepted = counts["blocking"], counts["warnings"], counts["accepted"]
    run.seconds = round(time.perf_counter() - started, 3)
    audit.record(
        db, action="validation.run", entity_type="material", entity_id=str(material.id), user_id=user.id if user else None, material_id=material.id,
        after={"run": str(run.id), "trigger": trigger, **counts, "rules_hash": run.rules_hash}, ip=ip,
    )
    await db.flush()
    return run


async def latest(db: AsyncSession, material: Material) -> ValidationRun | None:
    query = select(ValidationRun).where(ValidationRun.material_id == material.id).order_by(ValidationRun.created_at.desc()).limit(1)
    return (await db.execute(query)).scalar_one_or_none()


async def outdated(db: AsyncSession, material: Material, run: ValidationRun, rules: dict[str, ValidationRule] | None = None) -> dict[str, bool]:
    """Why a run no longer describes the CUF: its data changed since, or the rules' configuration."""
    rules = rules if rules is not None else await settings(db)
    return {"data": run.data_fingerprint != await fingerprint(db, material), "rules": run.rules_hash != rules_hash(rules)}


async def findings(db: AsyncSession, run: ValidationRun) -> list[ValidationFinding]:
    query = select(ValidationFinding).where(ValidationFinding.run_id == run.id).order_by(ValidationFinding.rule_code, ValidationFinding.location)
    return list((await db.execute(query)).scalars())


class AcceptError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


async def accept(db: AsyncSession, material: Material, finding: ValidationFinding, justification: str, user: User, ip: str | None) -> FindingAcceptance:
    """A warning accepted for this CUF: it counts as accepted in this run and in the next ones."""
    if finding.severity != WARNING:
        raise AcceptError("finding_blocking_cannot_be_accepted")
    if finding.acceptance_id is not None:
        raise AcceptError("finding_already_accepted")
    acceptance = FindingAcceptance(
        id=uuid.uuid4(), material_id=material.id, rule_code=finding.rule_code, entity_type=finding.entity_type, entity_id=finding.entity_id,
        problem=finding.problem, justification=justification, created_by=user.id,
    )
    db.add(acceptance)
    await db.flush()
    finding.acceptance_id = acceptance.id
    run = await db.get(ValidationRun, finding.run_id, with_for_update=True)
    if run is not None:
        run.warnings, run.accepted = max(0, run.warnings - 1), run.accepted + 1
    audit.record(
        db, action="validation.finding_accepted", entity_type="validation_finding", entity_id=str(finding.id), user_id=user.id, material_id=material.id,
        after={"rule": finding.rule_code, "location": finding.location, "problem": finding.problem, "justification": justification}, ip=ip,
    )
    return acceptance


async def delivery_problems(db: AsyncSession, material: Material) -> list[dict[str, Any]]:
    """Why the delivery is refused (empty: it may go)."""
    run = await latest(db, material)
    problems: list[dict[str, Any]] = []
    if run is None:
        problems.append({"code": "delivery_not_validated", "params": {}})
    else:
        stale = await outdated(db, material, run)
        if stale["data"] or stale["rules"]:
            problems.append({"code": "delivery_outdated", "params": {}})
        if run.blocking:
            problems.append({"code": "delivery_blocking", "params": {"count": run.blocking}})
    for guard in DELIVERY_GUARDS:
        problems += await guard(db, material)
    return problems


def summary(run: ValidationRun | None, stale: dict[str, bool] | None) -> dict[str, Any]:
    """The traffic light: red with blocking findings, amber with warnings, green otherwise; grey with no run."""
    if run is None:
        return {"state": "none", "outdated": False}
    state = "red" if run.blocking else "amber" if run.warnings or run.accepted else "green"
    return {
        "state": state, "outdated": bool(stale and (stale["data"] or stale["rules"])), "blocking": run.blocking, "warnings": run.warnings,
        "accepted": run.accepted, "at": run.created_at, "run_id": str(run.id),
    }


