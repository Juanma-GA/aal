"""Reference tables (E03, RNF-07): read by any signed-in user (the modules'
forms need them), edited only by an admin -- create a value, edit its
description, definition and attributes, activate and deactivate it,
reorder the table -- with optimistic locking and an audit row per change.
A value is never deleted (HR9). Export to Excel for anyone, import (the
two phases of app/services/import_jobs.py) for an admin."""

import dataclasses
import re
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, Request, Response, UploadFile, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, require_admin
from app.api.routes.imports import job_out
from app.api.routes.users import version_conflict
from app.core.errors import error_detail
from app.db.base import get_db
from app.io_excel.targets import get_target
from app.io_excel.writer import write_workbook
from app.models import (
    EDITABLE_FIELD_ATTRIBUTES,
    FIELD_COLUMNS,
    Article,
    ArticleFieldDefinition,
    ArticleLifeControl,
    ReferenceTable,
    ReferenceValue,
    User,
)
from app.models.article import LIFE_CODE_FIELD
from app.schemas.reference import (
    ArticleFieldOut,
    ArticleFieldUpdate,
    ImportJobOut,
    ReferenceOrderIn,
    ReferenceTableOut,
    ReferenceValueCreate,
    ReferenceValueOut,
    ReferenceValueUpdate,
)
from app.services import audit, import_jobs, revalidation
from app.services.article_fields import LIFE_FIELDS, NUMERIC, FieldDef, FieldError, coerce, field_defs
from app.services.reference import attribute_problem
from app.services.reference_import import (
    KIND,
    build_template,
    get_table,
    table_values,
    template_values,
    value_snapshot,
)
from app.services.snapshots import client_ip

router = APIRouter(prefix="/api", tags=["reference-tables"])
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _table_out(table: ReferenceTable, total: int, active: int) -> ReferenceTableOut:
    return ReferenceTableOut(
        code=table.code,
        name=table.name,
        source=table.source,
        note=table.note,
        editable=table.editable,
        attribute_schema=table.attribute_schema,
        value_count=total,
        active_count=active,
        version=table.version,
    )


def _value_out(v: ReferenceValue) -> ReferenceValueOut:
    return ReferenceValueOut(
        id=v.id,
        code=v.code,
        description=v.description,
        definition=v.definition,
        attributes=v.attributes,
        is_active=v.is_active,
        sort_order=v.sort_order,
        version=v.version,
        updated_at=v.updated_at,
    )


async def _counts(db: AsyncSession) -> dict[str, tuple[int, int]]:
    rows = await db.execute(
        select(ReferenceValue.table_code, func.count(), func.count().filter(ReferenceValue.is_active)).group_by(ReferenceValue.table_code)
    )
    return {code: (total, active) for code, total, active in rows}


def _not_editable() -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_detail("reference_table_not_editable"))


def _check_attributes(table: ReferenceTable, attributes: dict) -> None:
    problem = attribute_problem(table.attribute_schema, attributes)
    if problem:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=error_detail(problem[0], **problem[1]))


@router.get("/reference-tables", response_model=list[ReferenceTableOut])
async def list_tables(_user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> list[ReferenceTableOut]:
    counts = await _counts(db)
    tables = (await db.execute(select(ReferenceTable).order_by(ReferenceTable.sort_order, ReferenceTable.code))).scalars()
    return [_table_out(t, *counts.get(t.code, (0, 0))) for t in tables]


@router.get("/reference-tables/{code}", response_model=ReferenceTableOut)
async def get_reference_table(code: str, _user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> ReferenceTableOut:
    table = await get_table(db, code)
    return _table_out(table, *(await _counts(db)).get(code, (0, 0)))


@router.get("/reference-tables/{code}/values", response_model=list[ReferenceValueOut])
async def list_values(
    code: str,
    q: str | None = Query(default=None, max_length=200),
    active: bool | None = None,
    _user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ReferenceValueOut]:
    """Every value of the table, in its order; `q` matches the code, the
    description or the definition (any case), `active` filters by state."""
    await get_table(db, code)
    query = select(ReferenceValue).where(ReferenceValue.table_code == code)
    if q and q.strip():
        pattern = "%" + re.sub(r"([\\%_])", r"\\\1", q.strip()) + "%"
        query = query.where(
            or_(
                ReferenceValue.code.ilike(pattern, escape="\\"),
                ReferenceValue.description.ilike(pattern, escape="\\"),
                ReferenceValue.definition.ilike(pattern, escape="\\"),
            )
        )
    if active is not None:
        query = query.where(ReferenceValue.is_active.is_(active))
    values = (await db.execute(query.order_by(ReferenceValue.sort_order, ReferenceValue.code))).scalars()
    return [_value_out(v) for v in values]


@router.post("/reference-tables/{code}/values", response_model=ReferenceValueOut, status_code=status.HTTP_201_CREATED)
async def create_value(
    code: str, body: ReferenceValueCreate, request: Request, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
) -> ReferenceValueOut:
    table = await get_table(db, code, for_update=True)
    if not table.editable:
        raise _not_editable()
    _check_attributes(table, body.attributes)
    if (await db.execute(select(ReferenceValue.id).where(ReferenceValue.table_code == code, ReferenceValue.code == body.code))).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_detail("reference_value_exists"))
    last = (await db.execute(select(func.max(ReferenceValue.sort_order)).where(ReferenceValue.table_code == code))).scalar() or 0
    value = ReferenceValue(
        table_code=code,
        code=body.code,
        description=body.description,
        definition=body.definition or None,
        attributes=body.attributes,
        is_active=True,
        sort_order=last + 1,
        version=1,
    )
    db.add(value)
    table.version += 1
    await db.flush()
    audit.record(
        db, action="reference_value.created", entity_type="reference_value", entity_id=str(value.id),
        user_id=admin.id, after=value_snapshot(value), ip=client_ip(request),
    )
    run = await revalidation.after_table_change(db, code, admin.id)
    await db.commit()
    if run:
        revalidation.schedule(run)
    await db.refresh(value)
    return _value_out(value)


@router.patch("/reference-tables/{code}/values/{value_id}", response_model=ReferenceValueOut)
async def update_value(
    code: str,
    value_id: uuid.UUID,
    body: ReferenceValueUpdate,
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> ReferenceValueOut:
    table = await get_table(db, code)
    if not table.editable:
        raise _not_editable()
    value = (
        await db.execute(
            select(ReferenceValue).where(ReferenceValue.id == value_id, ReferenceValue.table_code == code).with_for_update()
        )
    ).scalar_one_or_none()
    if value is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_detail("reference_value_not_found"))
    if value.version != body.version:
        raise version_conflict(value.version)
    changes = body.model_dump(exclude_unset=True, exclude={"version"})
    if changes.get("description", "") is None or changes.get("attributes", {}) is None or changes.get("is_active", True) is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=error_detail("validation_error"))
    if "definition" in changes:
        changes["definition"] = changes["definition"] or None
    if "attributes" in changes:
        _check_attributes(table, changes["attributes"])
    before = value_snapshot(value)
    for name, new in changes.items():
        setattr(value, name, new)
    if value_snapshot(value) == before:
        return _value_out(value)
    value.version += 1
    if "is_active" in changes and changes["is_active"] != before["is_active"]:
        action = "reference_value.activated" if value.is_active else "reference_value.deactivated"
    else:
        action = "reference_value.updated"
    audit.record(
        db, action=action, entity_type="reference_value", entity_id=str(value.id),
        user_id=admin.id, before=before, after=value_snapshot(value), ip=client_ip(request),
    )
    # Only whether a code is active counts for the AR rules.
    run = await revalidation.after_table_change(db, code, admin.id) if action != "reference_value.updated" else None
    await db.commit()
    if run:
        revalidation.schedule(run)
    await db.refresh(value)
    return _value_out(value)


@router.put("/reference-tables/{code}/order", response_model=list[ReferenceValueOut])
async def reorder_values(
    code: str, body: ReferenceOrderIn, request: Request, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
) -> list[ReferenceValueOut]:
    table = await get_table(db, code, for_update=True)
    if not table.editable:
        raise _not_editable()
    if table.version != body.version:
        raise version_conflict(table.version)
    values = list(
        (await db.execute(select(ReferenceValue).where(ReferenceValue.table_code == code).order_by(ReferenceValue.sort_order, ReferenceValue.code).with_for_update())).scalars()
    )
    by_id = {v.id: v for v in values}
    if len(body.value_ids) != len(values) or set(body.value_ids) != set(by_id):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=error_detail("reference_order_mismatch"))
    before = [v.code for v in values]
    for position, value_id in enumerate(body.value_ids, start=1):
        if by_id[value_id].sort_order != position:
            by_id[value_id].sort_order = position
            by_id[value_id].version += 1
    table.version += 1
    audit.record(
        db, action="reference_table.reordered", entity_type="reference_table", entity_id=code,
        user_id=admin.id, before={"order": before}, after={"order": [by_id[i].code for i in body.value_ids]}, ip=client_ip(request),
    )
    await db.commit()
    return [_value_out(v) for v in await table_values(db, code)]


@router.get("/reference-tables/{code}/export")
async def export_table(code: str, _user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> Response:
    """The table as the "Tabla de referencia" template (every value, its
    order, active or not)."""
    table = await get_table(db, code)
    values = await table_values(db, code)
    data = write_workbook(build_template(table, [v.code for v in values]), [template_values(v) for v in values])
    return Response(content=data, media_type=XLSX, headers={"Content-Disposition": f'attachment; filename="{code}.xlsx"'})


@router.post("/reference-tables/{code}/import", response_model=ImportJobOut, status_code=status.HTTP_202_ACCEPTED)
async def import_table(
    code: str,
    background: BackgroundTasks,
    file: UploadFile = File(...),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> ImportJobOut:
    """Phase 1: the file is checked and analysed in the background; poll
    GET /api/import-jobs/{id} for the report."""
    table = await get_table(db, code)
    if not table.editable:
        raise _not_editable()
    data = await import_jobs.read_upload(file, await import_jobs.limits(db))
    job = await import_jobs.start(
        db, target=get_target(KIND), params={"table": code}, user=admin, file_name=file.filename, data=data
    )
    background.add_task(import_jobs.run_analysis, job.id)
    return job_out(job)


@router.get("/article-fields", response_model=list[ArticleFieldOut])
async def list_article_fields(_user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> list[ArticleFieldOut]:
    names = dict((await db.execute(select(ReferenceTable.code, ReferenceTable.name))).all())
    fields = (await db.execute(select(ArticleFieldDefinition).order_by(ArticleFieldDefinition.sort_order))).scalars()
    return [
        ArticleFieldOut(
            prisma_code=f.prisma_code,
            name=f.name,
            importance=f.importance,
            guide_field=f.guide_field,
            data_type=f.data_type,
            length=f.length,
            decimals=f.decimals,
            related_to=f.related_to,
            supplied_by_contractor=f.supplied_by_contractor,
            reference_table_code=f.reference_table_code,
            reference_table_name=names.get(f.reference_table_code) if f.reference_table_code else None,
            header=f.header,
            allowed_values=f.allowed_values,
            help=f.help,
            edited_by_admin=f.edited_by_admin,
            version=f.version,
        )
        for f in fields
    ]


# The NOC's length is its format (13, E10/E11), not a field's to correct.
_FIXED_LENGTH = {"cdART"}


def _field_snapshot(f: ArticleFieldDefinition) -> dict:
    return {name: getattr(f, name) for name in EDITABLE_FIELD_ATTRIBUTES}


async def _values_not_fitting(db: AsyncSession, definition: FieldDef) -> tuple[int, list[str]]:
    """How many live articles have a value the new definition refuses (and
    some of their names): a correction never leaves stored data invalid."""
    if definition.prisma in LIFE_FIELDS:
        column = ArticleLifeControl.unit_code if definition.prisma == LIFE_CODE_FIELD else ArticleLifeControl.quantity
        query = select(Article.nombre, column).join(ArticleLifeControl, ArticleLifeControl.article_id == Article.id)
    else:
        column = getattr(Article, FIELD_COLUMNS[definition.prisma])
        query = select(Article.nombre, column)
    rows = (await db.execute(query.where(Article.deleted_at.is_(None), column.is_not(None)))).all()
    names = []
    for name, value in rows:
        try:
            coerce(definition, value)
        except FieldError:
            names.append(name)
    return len(names), sorted(set(names))[:5]


@router.patch("/article-fields/{prisma_code}", response_model=ArticleFieldOut)
async def update_article_field(
    prisma_code: str, body: ArticleFieldUpdate, request: Request, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
) -> ArticleFieldOut:
    """The admin corrects a field definition without code (E13), audited;
    the articles are revalidated in the background when the change can
    alter their findings."""
    field = (await db.execute(select(ArticleFieldDefinition).where(ArticleFieldDefinition.prisma_code == prisma_code).with_for_update())).scalar_one_or_none()
    if field is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_detail("article_field_not_found"))
    if field.version != body.version:
        raise version_conflict(field.version)
    changes = {k: v for k, v in body.model_dump(exclude_unset=True, exclude={"version"}).items() if getattr(field, k) != v}
    for required in ("name", "importance", "length", "supplied_by_contractor"):
        if required in changes and changes[required] is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=error_detail("validation_error"))
    if ("length" in changes or "decimals" in changes) and prisma_code in _FIXED_LENGTH:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=error_detail("article_field_length_fixed"))
    numeric = field.data_type == NUMERIC
    length = changes.get("length", field.length)
    decimals = changes.get("decimals", field.decimals)
    if decimals and (not numeric or length is None or decimals >= length):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=error_detail("article_field_decimals_invalid"))
    if "reference_table_code" in changes and changes["reference_table_code"] is not None:
        if field.allowed_values or numeric:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=error_detail("article_field_table_not_allowed"))
        await get_table(db, changes["reference_table_code"])
    if not changes:
        return next(f for f in await list_article_fields(admin, db) if f.prisma_code == prisma_code)
    if "length" in changes or "decimals" in changes:
        current = (await field_defs(db))[prisma_code]
        count, names = await _values_not_fitting(db, dataclasses.replace(current, length=length, decimals=decimals))
        if count:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_detail("article_field_data_does_not_fit", count=count, names=", ".join(names)))
    before = _field_snapshot(field)
    for name, value in changes.items():
        setattr(field, name, value)
    field.edited_by_admin = True
    field.version += 1
    field.updated_at, field.updated_by = datetime.now(UTC), admin.id
    audit.record(
        db, action="article_field.updated", entity_type="article_field", entity_id=prisma_code,
        user_id=admin.id, before=before, after=_field_snapshot(field), ip=client_ip(request),
    )
    run = None
    if changes.keys() & {"importance", "length", "decimals", "reference_table_code"}:
        run = (await revalidation.request(db, "field_definition", {"field": prisma_code}, admin.id)).id
    await db.commit()
    if run:
        revalidation.schedule(run)
    return next(f for f in await list_article_fields(admin, db) if f.prisma_code == prisma_code)
