"""Articles (E12, RF-04): the single article master, global (D16) like the
catalog -- no material in the URL.

Reading is for any signed-in user (articulos.ver is every role's); editing
needs articulos.editar in some material (app/services/articles.py), and
importing is the admin's. Every change is audited; writes go with the
article's version (409 when someone else changed it meanwhile).
"""

import asyncio
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, Request, Response, UploadFile, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, require_admin
from app.api.routes.catalog import XLSX, like_text
from app.api.routes.imports import job_out
from app.api.routes.users import confirmation_required, version_conflict
from app.core.errors import error_detail
from app.db.base import get_db
from app.io_excel.targets import get_target
from app.io_excel.writer import write_workbook
from app.models import FIELD_COLUMNS, MAX_LIFE_CONTROLS, Article, ArticleReference, AuditLog, User
from app.models.article import LIFE_CODE_FIELD, LIFE_QUANTITY_FIELD
from app.schemas.articles import (
    ArticleIn,
    ArticleOut,
    ArticlePage,
    ArticleRights,
    ArticleRow,
    ArticleUpdate,
    BatchIn,
    BatchResult,
    ExportSummary,
    LifeControlIn,
    LifeControlOut,
    ReferenceIn,
    ReferenceOut,
    ReferenceUpdate,
)
from app.schemas.reference import ImportJobOut
from app.services import audit, confunfis, import_jobs
from app.services import confunfis_extras as extras
from app.services.article_fields import FieldError, coerce
from app.services.article_import import FICHERO_CARGA, MAESTRO, build_template, export_values, reference_rows, references_template
from app.services.articles import (
    Checker,
    can_edit_articles,
    data_of,
    life_of,
    normalize_identity,
    reference_owner,
    reference_snapshot,
    set_data,
    set_life,
    set_principal,
    snapshot,
    where_used,
)
from app.services.parameters import get_parameter
from app.services.snapshots import client_ip
from app.validacion.articulos import RULES, LifeControl, autocorrect

router = APIRouter(prefix="/api/articles", tags=["articles"])

TEMPLATES = {"fichero_carga": FICHERO_CARGA, "maestro": MAESTRO}
_FILE_NAMES = {FICHERO_CARGA: "FICHERO_CARGA", MAESTRO: "MAESTRO_AAL"}
# Identification is not among `fields`: it has its own keys.
_NOT_A_FIELD = ("cdART", "NomArt", LIFE_CODE_FIELD, LIFE_QUANTITY_FIELD)
# The rules an article can be filtered by (AR-008 corrects, it is no finding).
_RULE_PATTERN = "^(" + "|".join(re.escape(code) for code, rule in RULES.items() if rule.severity != "autocorreccion") + ")$"


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_detail("article_not_found"))


def _taken() -> HTTPException:
    """The NOC or P/N + NCAGE was taken meanwhile (the unique index caught it)."""
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_detail("article_identity_taken"))


def _invalid(problems: list[dict[str, Any]]) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=error_detail("article_invalid", problems=problems))


async def _require_editor(db: AsyncSession, user: User) -> None:
    if not await can_edit_articles(db, user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_detail("permission_denied", permission="articulos.editar"))


def _plain(value: Any) -> Any:
    return None if value is None else str(value) if not isinstance(value, (str, bool)) else value


def _row(a: Article) -> ArticleRow:
    return ArticleRow(
        id=a.id, noc=a.noc, pn=a.pn, ncage=a.ncage, nombre=a.nombre, origen_nombre=a.origen_nombre,
        fields={p: _plain(v) for p, v in data_of(a).items() if p not in _NOT_A_FIELD},
        life_controls=[LifeControlOut(position=c.position, unit_code=c.unit_code, quantity=_plain(c.quantity)) for c in a.life_controls],
        finding_codes=list(a.finding_codes), version=a.version,
    )


def _reference_out(r: ArticleReference) -> ReferenceOut:
    return ReferenceOut(id=r.id, pn=r.pn, ncage=r.ncage, principal=r.principal, origin=r.origin, version=r.version, created_at=r.created_at, updated_at=r.updated_at)


async def _names(db: AsyncSession, ids: set[uuid.UUID | None]) -> dict[uuid.UUID, str]:
    ids = {i for i in ids if i}
    return dict((await db.execute(select(User.id, User.display_name).where(User.id.in_(ids)))).all()) if ids else {}


async def _out(db: AsyncSession, a: Article, checker: Checker, user: User, corrections: list[dict[str, Any]] | None = None) -> ArticleOut:
    names = await _names(db, {a.created_by, a.updated_by})
    return ArticleOut(
        **_row(a).model_dump(),
        references=[_reference_out(r) for r in a.live_references],
        # Checked now: a reference table may have changed since it was saved.
        findings=checker.findings(data_of(a), life_of(a)),
        where_used=await where_used(db, a, user),
        corrections=corrections or [],
        created_at=a.created_at, updated_at=a.updated_at, created_by=names.get(a.created_by), updated_by=names.get(a.updated_by),
    )


async def _one(db: AsyncSession, article_id: uuid.UUID, *, lock: bool = False) -> Article:
    query = select(Article).where(Article.id == article_id, Article.deleted_at.is_(None))
    found = (await db.execute(query.with_for_update() if lock else query)).scalar_one_or_none()
    if found is None:
        raise _not_found()
    return found


def _check_code(checker: Checker, prisma: str, value: Any, stored: Any, problems: list[dict[str, Any]]) -> None:
    """A new code must be an active one of its table; the stored one stays valid."""
    d = checker.defs[prisma]
    table = d.table if not d.allowed_values else None
    if table is None or value is None or value == stored:
        return
    if not checker.references.get(table, {}).get(str(value)):
        problems.append({"field": prisma, "code": "not_in_table", "params": {"table": table}})


def _coerced_fields(checker: Checker, article: Article | None, fields: dict[str, Any], problems: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    stored = data_of(article) if article else {}
    for prisma, raw in fields.items():
        if prisma not in checker.defs or prisma in _NOT_A_FIELD:
            problems.append({"field": prisma, "code": "unknown_field", "params": {}})
            continue
        try:
            value = coerce(checker.defs[prisma], raw)
        except FieldError as exc:
            problems.append({"field": prisma, "code": exc.code, "params": exc.params})
            continue
        _check_code(checker, prisma, value, stored.get(prisma), problems)
        out[prisma] = value
    return out


def _coerced_life(checker: Checker, article: Article | None, life: list[LifeControlIn], problems: list[dict[str, Any]]) -> list[LifeControl]:
    stored = {c.unit_code for c in life_of(article)} if article else set()
    out = []
    for position, c in enumerate(life, start=1):
        try:
            code = coerce(checker.defs[LIFE_CODE_FIELD], c.unit_code)
            quantity = coerce(checker.defs[LIFE_QUANTITY_FIELD], c.quantity)
        except FieldError as exc:
            problems.append({"field": exc.prisma, "code": exc.code, "params": {**exc.params, "position": position}})
            continue
        if code is not None and code not in stored and not checker.references.get("D114", {}).get(str(code)):
            problems.append({"field": LIFE_CODE_FIELD, "code": "not_in_table", "params": {"table": "D114", "position": position}})
        out.append(LifeControl(code, quantity))
    return out


async def _check_unique(db: AsyncSession, article_id: uuid.UUID | None, noc: str | None, pn: str | None, ncage: str | None) -> None:
    others = [Article.deleted_at.is_(None)] + ([Article.id != article_id] if article_id else [])
    if noc and (await db.execute(select(Article.id).where(Article.noc == noc, *others))).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_detail("article_noc_taken"))
    if pn and await reference_owner(db, pn, ncage, exclude=article_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_detail("article_pn_ncage_taken"))


def _identity(noc: Any, pn: Any, ncage: Any, nombre: str | None, problems: list[dict[str, Any]], checker: Checker) -> tuple[Any, Any, Any, Any]:
    noc, pn, ncage, wrong = normalize_identity(noc, pn, ncage)
    problems += [{"field": w, "code": f"{w}_invalid", "params": {}} for w in wrong]
    if ncage and not pn:
        # A reference is a P/N (E13): an NCAGE alone has nowhere to go.
        problems.append({"field": "pn", "code": "pn_required", "params": {}})
    name = None
    if nombre is not None:
        try:
            name = coerce(checker.defs["NomArt"], nombre)
        except FieldError as exc:
            problems.append({"field": "nombre", "code": exc.code, "params": exc.params})
        if name is None and not any(p["field"] == "nombre" for p in problems):
            problems.append({"field": "nombre", "code": "required", "params": {}})
    return noc, pn, ncage, name


def _filters(
    q: str | None, rule: str | None, with_findings: bool | None, no_noc: bool | None, repairable: str | None,
    life_control: str | None, group: str | None, ids: list[uuid.UUID] | None,
) -> list[Any]:
    where: list[Any] = [Article.deleted_at.is_(None)]
    if q and q.strip():
        like = f"%{like_text(q.strip())}%"
        by_pn = select(ArticleReference.article_id).where(ArticleReference.pn.ilike(like), ArticleReference.deleted_at.is_(None))
        where.append(or_(Article.noc.ilike(like), Article.nombre.ilike(like), Article.id.in_(by_pn)))
    if rule:
        where.append(Article.finding_codes.contains([rule]))
    if with_findings is not None:
        where.append((func.cardinality(Article.finding_codes) > 0) if with_findings else (func.cardinality(Article.finding_codes) == 0))
    if no_noc:
        where.append(Article.noc.is_(None))
    if repairable:
        where.append(Article.reparable == repairable)
    if life_control:
        where.append(Article.control_vida == life_control)
    if group:
        where.append(Article.grupo_estructural == group)
    if ids:
        where.append(Article.id.in_(ids))
    return where


class Filters:
    """The list's filters, shared by the list, the export and its summary."""

    def __init__(
        self,
        q: str | None = Query(default=None, max_length=100),
        rule: str | None = Query(default=None, pattern=_RULE_PATTERN),
        with_findings: bool | None = None,
        no_noc: bool | None = None,
        repairable: str | None = Query(default=None, pattern="^[SN]$"),
        life_control: str | None = Query(default=None, pattern="^[SN]$"),
        group: str | None = Query(default=None, max_length=1),
        ids: list[uuid.UUID] | None = Query(default=None, max_length=5000),
    ):
        self.where = _filters(q, rule, with_findings, no_noc, repairable, life_control, group, ids)


@router.get("/rights", response_model=ArticleRights)
async def rights(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> ArticleRights:
    params = await get_parameter(db, "articles")
    return ArticleRights(
        can_edit=await can_edit_articles(db, user), can_import=user.is_admin, max_batch_rows=params["max_batch_rows"], max_life_controls=MAX_LIFE_CONTROLS
    )


@router.get("", response_model=ArticlePage)
async def list_articles(
    filters: Filters = Depends(),
    page: int = Query(default=1, ge=1),
    page_size: int | None = Query(default=None, ge=1),
    _user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> ArticlePage:
    params = await get_parameter(db, "articles")
    size = page_size or params["page_size"]
    if size > params["max_page_size"]:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=error_detail("page_size_too_large", max_page_size=params["max_page_size"]))
    total = await db.scalar(select(func.count()).select_from(Article).where(*filters.where)) or 0
    rows = (
        await db.execute(select(Article).where(*filters.where).order_by(Article.nombre, Article.noc, Article.id).offset((page - 1) * size).limit(size))
    ).scalars().all()
    return ArticlePage(total=total, page=page, page_size=size, items=[_row(a) for a in rows])


@router.get("/export-summary", response_model=ExportSummary)
async def export_summary(filters: Filters = Depends(), _user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> ExportSummary:
    """Before exporting: how many articles go, and how many break an AR rule
    (the export is not blocked in E12; the SIGLE package will be)."""
    codes = (await db.execute(select(Article.finding_codes).where(*filters.where))).scalars().all()
    by_rule = {code: sum(1 for c in codes if code in c) for code in RULES if code != "AR-008"}
    return ExportSummary(articles=len(codes), with_findings=sum(1 for c in codes if c), by_rule=by_rule)


@router.get("/export")
async def export_articles(
    template: str = Query(pattern="^(fichero_carga|maestro)$"),
    filters: Filters = Depends(),
    _user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    kind = TEMPLATES[template]
    checker = await Checker.load(db)
    rows = (await db.execute(select(Article).where(*filters.where).order_by(Article.nombre, Article.noc, Article.id))).scalars().all()
    extra = [(references_template(), reference_rows(list(rows)))] if kind == MAESTRO else []
    data = await asyncio.to_thread(write_workbook, build_template(checker.defs, kind), [export_values(a, kind) for a in rows], extra)
    name = f"{_FILE_NAMES[kind]}_{datetime.now(UTC):%Y%m%d}.xlsx"
    return Response(content=data, media_type=XLSX, headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.post("/import", response_model=ImportJobOut, status_code=status.HTTP_202_ACCEPTED)
async def import_articles(
    background: BackgroundTasks,
    template: str = Query(pattern="^(fichero_carga|maestro)$"),
    file: UploadFile = File(...),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> ImportJobOut:
    """Phase 1: analysed in the background; poll /api/import-jobs/{id} and
    apply it there."""
    data = await import_jobs.read_upload(file, await import_jobs.limits(db))
    job = await import_jobs.start(db, target=get_target(TEMPLATES[template]), params={}, user=admin, file_name=file.filename, data=data)
    background.add_task(import_jobs.run_analysis, job.id)
    return job_out(job)


@router.post("", response_model=ArticleOut, status_code=status.HTTP_201_CREATED)
async def create_article(body: ArticleIn, request: Request, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> ArticleOut:
    await _require_editor(db, user)
    checker = await Checker.load(db)
    problems: list[dict[str, Any]] = []
    noc, pn, ncage, name = _identity(body.noc, body.pn, body.ncage, body.nombre, problems, checker)
    fields = _coerced_fields(checker, None, body.fields, problems)
    life = _coerced_life(checker, None, body.life_controls, problems)
    if problems:
        raise _invalid(problems)
    await _check_unique(db, None, noc, pn, ncage)
    data = {**{p: None for p in FIELD_COLUMNS}, **fields, "cdART": noc, "NomArt": name}
    corrections = autocorrect(data)
    article = Article(id=uuid.uuid4(), origen_nombre=body.origen_nombre, nombre=name, version=1, created_by=user.id, updated_by=user.id, references=[], life_controls=[])
    set_data(article, data)
    set_life(article, life)
    checker.recheck(article)
    db.add(article)
    await set_principal(db, article, pn, ncage, user.id, "manual")
    try:
        await db.flush()
    except IntegrityError:
        raise _taken() from None
    audit.record(
        db, action="article.created", entity_type="article", entity_id=str(article.id), user_id=user.id,
        after={**snapshot(article), "corrections": corrections}, ip=client_ip(request),
    )
    await db.commit()
    return await _out(db, await _one(db, article.id), checker, user, corrections)


async def _update(db: AsyncSession, article: Article, body: ArticleUpdate | Any, checker: Checker, user: User, request: Request) -> list[dict[str, Any]]:
    """Applies a change to a locked article (its version already checked);
    raises 422/409 before touching it."""
    problems: list[dict[str, Any]] = []
    sent = body.model_fields_set
    if "nombre" in sent and getattr(body, "nombre", None) is None:
        problems.append({"field": "nombre", "code": "required", "params": {}})
    noc, pn, ncage, name = _identity(
        body.noc if "noc" in sent else article.noc, body.pn if "pn" in sent else article.pn,
        body.ncage if "ncage" in sent else article.ncage, getattr(body, "nombre", None) if "nombre" in sent else article.nombre, problems, checker,
    )
    fields = _coerced_fields(checker, article, body.fields, problems)
    life = _coerced_life(checker, article, body.life_controls, problems) if getattr(body, "life_controls", None) is not None else None
    if problems:
        raise _invalid(problems)
    await _check_unique(db, article.id, noc, pn, ncage)
    before = snapshot(article)
    data = {**data_of(article), **fields, "cdART": noc, "NomArt": name}
    corrections = autocorrect(data)
    set_data(article, data)
    await set_principal(db, article, pn, ncage, user.id, "manual")
    if "origen_nombre" in sent and body.origen_nombre:
        article.origen_nombre = body.origen_nombre
    if life is not None:
        set_life(article, life)
    checker.recheck(article)
    article.version += 1
    article.updated_by = user.id
    audit.record(
        db, action="article.updated", entity_type="article", entity_id=str(article.id), user_id=user.id,
        before=before, after={**snapshot(article), "corrections": corrections}, ip=client_ip(request),
    )
    return corrections


@router.get("/{article_id}", response_model=ArticleOut)
async def get_article(article_id: uuid.UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> ArticleOut:
    return await _out(db, await _one(db, article_id), await Checker.load(db), user)


@router.patch("/{article_id}", response_model=ArticleOut)
async def update_article(
    article_id: uuid.UUID, body: ArticleUpdate, request: Request, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
) -> ArticleOut:
    await _require_editor(db, user)
    checker = await Checker.load(db)
    article = await _one(db, article_id, lock=True)
    if article.version != body.version:
        raise version_conflict(article.version)
    corrections = await _update(db, article, body, checker, user, request)
    try:
        await db.flush()
    except IntegrityError:
        raise _taken() from None
    await confunfis.refresh_materials(db, article_ids={article_id})
    await db.commit()
    return await _out(db, await _one(db, article_id), checker, user, corrections)


@router.post("/batch", response_model=list[BatchResult])
async def batch_update(body: BatchIn, request: Request, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> list[BatchResult]:
    """The grid's save: each row on its own, with its version. A row someone
    else changed meanwhile (or that is invalid) is reported and left as it
    is; the others are saved (one transaction, each row in a savepoint)."""
    await _require_editor(db, user)
    limit = (await get_parameter(db, "articles"))["max_batch_rows"]
    if len(body.items) > limit:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=error_detail("batch_too_large", max=limit))
    checker = await Checker.load(db)
    results: dict[uuid.UUID, BatchResult] = {}
    # Locked in one order (by id): two saves never wait on each other's rows.
    for item in sorted(body.items, key=lambda i: str(i.id)):
        try:
            async with db.begin_nested():
                article = await _one(db, item.id, lock=True)
                if article.version != item.version:
                    raise version_conflict(article.version)
                await _update(db, article, item, checker, user, request)
                try:
                    await db.flush()
                except IntegrityError:
                    raise _taken() from None
            results[item.id] = BatchResult(id=item.id, ok=True, article=_row(article))
        except HTTPException as exc:
            results[item.id] = BatchResult(id=item.id, ok=False, error=exc.detail if isinstance(exc.detail, dict) else {"code": "error"})
    await confunfis.refresh_materials(db, article_ids={i for i, r in results.items() if r.ok})
    await db.commit()
    return [results[i.id] for i in body.items]


@router.delete("/{article_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_article(
    article_id: uuid.UUID, version: int, request: Request, confirm: bool = False, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
) -> None:
    """Deleted logically (HR9); its history stays."""
    await _require_editor(db, user)
    if not confirm:
        raise confirmation_required()
    article = await _one(db, article_id, lock=True)
    if article.version != version:
        raise version_conflict(article.version)
    used = await confunfis.rows_using_article(db, article.id)
    if used:
        # A CONFUNFIS row is this component: it goes first (E13).
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_detail("article_in_confunfis", count=len(used), rows=confunfis.rows_text(used)))
    parents = await extras.parents_of(db, article.id)
    if parents:
        # It is a part of another article (E14): that breakdown changes first.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_detail("article_is_part", articles=parents))
    ip = client_ip(request)
    # Its own breakdown goes with it, each part audited (E14).
    for part in await extras.live_parts(db, article.id):
        await extras.remove_part(db, part, user.id, ip)
    await extras.unlink_products(db, article.id)
    before = snapshot(article)
    article.deleted_at = datetime.now(UTC)
    # Its P/N + NCAGE go with it: free for another article (uq_article_reference_pn_ncage).
    for r in article.live_references:
        r.deleted_at, r.version, r.updated_by = article.deleted_at, r.version + 1, user.id
    article.version += 1
    article.updated_by = user.id
    audit.record(db, action="article.deleted", entity_type="article", entity_id=str(article.id), user_id=user.id, before=before, after=None, ip=ip)
    await extras.refresh_parts(db)
    await db.commit()


@router.get("/{article_id}/findings")
async def article_findings(article_id: uuid.UUID, _user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    article = await _one(db, article_id)
    return (await Checker.load(db)).findings(data_of(article), life_of(article))


@router.get("/{article_id}/history")
async def article_history(article_id: uuid.UUID, _user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    """The article's audit, newest first."""
    await _one(db, article_id)
    rows = (
        await db.execute(
            select(AuditLog, User.display_name)
            .outerjoin(User, User.id == AuditLog.user_id)
            .where(AuditLog.entity_type == "article", AuditLog.entity_id == str(article_id))
            .order_by(AuditLog.created_at.desc())
        )
    ).all()
    return [{"id": str(r.id), "at": r.created_at.isoformat(), "action": r.action, "user": name, "before": r.before, "after": r.after} for r, name in rows]


# References (E13, NT §9.1.6): one article, several P/N + NCAGE. Each change
# goes with the reference's version and counts as a change of the article
# (its version goes up: the list shows the principal one), audited on it.


def _reference(article: Article, reference_id: uuid.UUID) -> ArticleReference:
    found = next((r for r in article.live_references if r.id == reference_id), None)
    if found is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_detail("article_reference_not_found"))
    return found


async def _reference_identity(db: AsyncSession, article: Article, pn: Any, ncage: Any, exclude: ArticleReference | None) -> tuple[str, str | None]:
    _noc, pn, ncage, wrong = normalize_identity(None, pn, ncage)
    problems = [{"field": w, "code": f"{w}_invalid", "params": {}} for w in wrong]
    if not pn:
        problems.append({"field": "pn", "code": "pn_required", "params": {}})
    if problems:
        raise _invalid(problems)
    same = [r for r in article.live_references if r is not exclude and (r.pn, r.ncage) == (pn, ncage)]
    if same or await reference_owner(db, pn, ncage, exclude=article.id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_detail("article_pn_ncage_taken"))
    return pn, ncage


async def _reference_changed(
    db: AsyncSession, article: Article, user: User, request: Request, action: str, before: dict[str, Any] | None, after: dict[str, Any] | None
) -> ArticleOut:
    article_id = article.id
    article.version += 1
    article.updated_by = user.id
    audit.record(
        db, action=action, entity_type="article", entity_id=str(article.id), user_id=user.id,
        before={"reference": before} if before else None, after={"reference": after} if after else None, ip=client_ip(request),
    )
    try:
        await db.flush()
    except IntegrityError:
        raise _taken() from None
    await confunfis.refresh_materials(db, article_ids={article_id})
    await db.commit()
    # Their server-side defaults and onupdate timestamps, loaded here (no lazy IO).
    for r in article.references:
        await db.refresh(r)
    await db.refresh(article)
    return await _out(db, await _one(db, article_id), await Checker.load(db), user)


async def _demote_principal(db: AsyncSession, article: Article, user: User) -> None:
    current = article.principal_reference
    if current is not None:
        current.principal, current.version, current.updated_by = False, current.version + 1, user.id
        await db.flush()


@router.post("/{article_id}/references", response_model=ArticleOut, status_code=status.HTTP_201_CREATED)
async def add_reference(
    article_id: uuid.UUID, body: ReferenceIn, request: Request, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
) -> ArticleOut:
    await _require_editor(db, user)
    article = await _one(db, article_id, lock=True)
    pn, ncage = await _reference_identity(db, article, body.pn, body.ncage, None)
    # The first reference is the principal one.
    principal = body.principal or article.principal_reference is None
    if principal:
        await _demote_principal(db, article, user)
    reference = ArticleReference(id=uuid.uuid4(), pn=pn, ncage=ncage, principal=principal, origin="manual", version=1, created_by=user.id, updated_by=user.id)
    article.references.append(reference)
    return await _reference_changed(db, article, user, request, "article.reference_added", None, reference_snapshot(reference))


@router.patch("/{article_id}/references/{reference_id}", response_model=ArticleOut)
async def update_reference(
    article_id: uuid.UUID, reference_id: uuid.UUID, body: ReferenceUpdate, request: Request,
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
) -> ArticleOut:
    await _require_editor(db, user)
    article = await _one(db, article_id, lock=True)
    reference = _reference(article, reference_id)
    if reference.version != body.version:
        raise version_conflict(reference.version)
    sent = body.model_fields_set
    before = reference_snapshot(reference)
    if ("pn" in sent and body.pn != reference.pn) or ("ncage" in sent and body.ncage != reference.ncage):
        used = await confunfis.rows_using_reference(db, reference.id)
        if used:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_detail("article_reference_in_confunfis", count=len(used), rows=confunfis.rows_text(used)))
    if await extras.parts_using_reference(db, reference.id):
        # A part of another article is that P/N (E14).
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_detail("article_reference_in_parts"))
    if "pn" in sent or "ncage" in sent:
        reference.pn, reference.ncage = await _reference_identity(
            db, article, body.pn if "pn" in sent else reference.pn, body.ncage if "ncage" in sent else reference.ncage, reference
        )
    if body.principal is True and not reference.principal:
        await _demote_principal(db, article, user)
        reference.principal = True
    elif body.principal is False:
        reference.principal = False
    reference.version += 1
    reference.updated_by = user.id
    return await _reference_changed(db, article, user, request, "article.reference_updated", before, reference_snapshot(reference))


@router.delete("/{article_id}/references/{reference_id}", response_model=ArticleOut)
async def remove_reference(
    article_id: uuid.UUID, reference_id: uuid.UUID, version: int, request: Request, confirm: bool = False,
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
) -> ArticleOut:
    """Removed logically (HR9). Removing the principal leaves none: another
    one is made principal explicitly."""
    await _require_editor(db, user)
    if not confirm:
        raise confirmation_required()
    article = await _one(db, article_id, lock=True)
    reference = _reference(article, reference_id)
    if reference.version != version:
        raise version_conflict(reference.version)
    used = await confunfis.rows_using_reference(db, reference.id)
    if used:
        # Those rows are that P/N (E13): they change first.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_detail("article_reference_in_confunfis", count=len(used), rows=confunfis.rows_text(used)))
    if await extras.parts_using_reference(db, reference.id):
        # A part of another article is that P/N (E14).
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_detail("article_reference_in_parts"))
    before = reference_snapshot(reference)
    reference.deleted_at, reference.version, reference.updated_by = datetime.now(UTC), reference.version + 1, user.id
    return await _reference_changed(db, article, user, request, "article.reference_removed", before, None)
