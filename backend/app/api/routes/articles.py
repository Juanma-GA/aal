"""Articles (E12, RF-04): the single article master, global (D16) like the
catalog -- no material in the URL.

Reading is for any signed-in user (articulos.ver is every role's); editing
needs articulos.editar in some material (app/services/articles.py), and
importing is the admin's. Every change is audited; writes go with the
article's version (409 when someone else changed it meanwhile).
"""

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, Request, Response, UploadFile, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, require_admin
from app.api.routes.catalog import XLSX, like_text
from app.api.routes.imports import job_out
from app.api.routes.users import confirmation_required, version_conflict
from app.core.errors import error_detail
from app.db.base import get_db
from app.io_excel.targets import get_target
from app.io_excel.writer import write_workbook
from app.models import FIELD_COLUMNS, Article, AuditLog, User
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
)
from app.schemas.reference import ImportJobOut
from app.services import audit, import_jobs
from app.services.article_fields import FieldError, coerce
from app.services.article_import import FICHERO_CARGA, MAESTRO, build_template, export_values
from app.services.articles import Checker, can_edit_articles, data_of, life_of, normalize_identity, set_data, set_life, snapshot, where_used
from app.services.parameters import get_parameter
from app.services.snapshots import client_ip
from app.validacion.articulos import RULES, LifeControl, autocorrect

router = APIRouter(prefix="/api/articles", tags=["articles"])

TEMPLATES = {"fichero_carga": FICHERO_CARGA, "maestro": MAESTRO}
_FILE_NAMES = {FICHERO_CARGA: "FICHERO_CARGA", MAESTRO: "MAESTRO_AAL"}
# Identification is not among `fields`: it has its own keys.
_NOT_A_FIELD = ("cdART", "NomArt", LIFE_CODE_FIELD, LIFE_QUANTITY_FIELD)


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_detail("article_not_found"))


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


async def _names(db: AsyncSession, ids: set[uuid.UUID | None]) -> dict[uuid.UUID, str]:
    ids = {i for i in ids if i}
    return dict((await db.execute(select(User.id, User.display_name).where(User.id.in_(ids)))).all()) if ids else {}


async def _out(db: AsyncSession, a: Article, checker: Checker, corrections: list[dict[str, Any]] | None = None) -> ArticleOut:
    names = await _names(db, {a.created_by, a.updated_by})
    return ArticleOut(
        **_row(a).model_dump(),
        # Checked now: a reference table may have changed since it was saved.
        findings=checker.findings(data_of(a), life_of(a)),
        where_used=await where_used(db, a),
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
    if pn and ncage and (await db.execute(select(Article.id).where(Article.pn == pn, Article.ncage == ncage, *others))).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_detail("article_pn_ncage_taken"))


def _identity(noc: Any, pn: Any, ncage: Any, nombre: str | None, problems: list[dict[str, Any]], checker: Checker) -> tuple[Any, Any, Any, Any]:
    noc, pn, ncage, wrong = normalize_identity(noc, pn, ncage)
    problems += [{"field": w, "code": f"{w}_invalid", "params": {}} for w in wrong]
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
        where.append(or_(Article.noc.ilike(like), Article.pn.ilike(like), Article.nombre.ilike(like)))
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
        rule: str | None = Query(default=None, pattern=r"^AR-00[1-7]$"),
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
    return ArticleRights(can_edit=await can_edit_articles(db, user), can_import=user.is_admin)


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
    data = await asyncio.to_thread(write_workbook, build_template(checker.defs, kind), [export_values(a, kind) for a in rows])
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
    article = Article(id=uuid.uuid4(), pn=pn, ncage=ncage, origen_nombre=body.origen_nombre, nombre=name, version=1, created_by=user.id, updated_by=user.id)
    set_data(article, data)
    set_life(article, life)
    checker.recheck(article)
    db.add(article)
    await db.flush()
    audit.record(
        db, action="article.created", entity_type="article", entity_id=str(article.id), user_id=user.id,
        after={**snapshot(article), "corrections": corrections}, ip=client_ip(request),
    )
    await db.commit()
    return await _out(db, await _one(db, article.id), checker, corrections)


async def _update(db: AsyncSession, article: Article, body: ArticleUpdate | Any, checker: Checker, user: User, request: Request) -> list[dict[str, Any]]:
    """Applies a change to a locked article (its version already checked);
    raises 422/409 before touching it."""
    problems: list[dict[str, Any]] = []
    sent = body.model_fields_set
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
    article.pn, article.ncage = pn, ncage
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
async def get_article(article_id: uuid.UUID, _user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> ArticleOut:
    return await _out(db, await _one(db, article_id), await Checker.load(db))


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
    await db.commit()
    return await _out(db, await _one(db, article_id), checker, corrections)


@router.post("/batch", response_model=list[BatchResult])
async def batch_update(body: BatchIn, request: Request, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> list[BatchResult]:
    """The grid's save: each row on its own, with its version. A row someone
    else changed meanwhile (or that is invalid) is reported and left as it
    is; the others are saved (one transaction, each row in a savepoint)."""
    await _require_editor(db, user)
    checker = await Checker.load(db)
    results: list[BatchResult] = []
    for item in body.items:
        try:
            async with db.begin_nested():
                article = await _one(db, item.id, lock=True)
                if article.version != item.version:
                    raise version_conflict(article.version)
                await _update(db, article, item, checker, user, request)
                await db.flush()
            results.append(BatchResult(id=item.id, ok=True, article=_row(article)))
        except HTTPException as exc:
            results.append(BatchResult(id=item.id, ok=False, error=exc.detail if isinstance(exc.detail, dict) else {"code": "error"}))
    await db.commit()
    return results


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
    before = snapshot(article)
    article.deleted_at = datetime.now(UTC)
    article.version += 1
    article.updated_by = user.id
    audit.record(db, action="article.deleted", entity_type="article", entity_id=str(article.id), user_id=user.id, before=before, after=None, ip=client_ip(request))
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
