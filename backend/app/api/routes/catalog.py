"""The normalized functional configuration (E10): every catalog version,
read by any signed-in user (the CUFs of E11 and the CONFUNFIS of E13 use
it); importing a new version (app/services/catalog_import.py, the two
phases of app/services/import_jobs.py) is for an admin. The tree is loaded
level by level: a request never sends the whole catalog."""

import asyncio
import re
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, Response, UploadFile, status
from sqlalchemy import distinct, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, require_admin
from app.api.routes.imports import job_out
from app.core.errors import error_detail
from app.db.base import get_db
from app.io_excel.targets import get_target
from app.io_excel.writer import write_workbook
from app.models import CatalogVersion, MaterialCategory, MaterialSubcategory, SnsExtraName, SnsPosition, SubcategorySns, User
from app.schemas.catalog import (
    CatalogVersionOut,
    CategoriesOut,
    CategoryOut,
    DiffItem,
    DiffOut,
    ExtraName,
    SearchHit,
    SearchPage,
    SnsAppearance,
    SnsDetail,
    SnsLink,
    SubcategoryOut,
    TreeNode,
    WarningsOut,
)
from app.schemas.reference import ImportJobOut
from app.services import import_jobs
from app.services.catalog import WARNING_CODES
from app.services.catalog_import import KIND, TEMPLATE, comparable_positions, compare, export_rows
from app.services.catalog_tree import tree_level as level_of_tree
from app.services.parameters import get_parameter

router = APIRouter(prefix="/api/catalog", tags=["catalog"])
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_CHANGES = ("new", "modified", "removed")


def _not_found(code: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_detail(code))


async def _version(db: AsyncSession, version_id: uuid.UUID) -> CatalogVersion:
    version = await db.get(CatalogVersion, version_id)
    if version is None:
        raise _not_found("catalog_version_not_found")
    return version


def _version_out(v: CatalogVersion, imported_by: str | None) -> CatalogVersionOut:
    return CatalogVersionOut(
        id=v.id, number=v.number, label=v.label, file_name=v.file_name, imported_at=v.imported_at, imported_by=imported_by,
        is_active=v.is_active, counts=v.counts, notes=v.notes, version=v.version,
    )


async def catalog_page_size(db: AsyncSession, page_size: int | None) -> int:
    params = await get_parameter(db, "catalog")
    size = page_size or params["page_size"]
    if size > params["max_page_size"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=error_detail("page_size_too_large", max_page_size=params["max_page_size"])
        )
    return size


def like_text(text: str) -> str:
    return re.sub(r"([\\%_])", r"\\\1", text)


@router.get("/versions", response_model=list[CatalogVersionOut])
async def list_versions(_user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> list[CatalogVersionOut]:
    rows = await db.execute(
        select(CatalogVersion, User.display_name).outerjoin(User, User.id == CatalogVersion.user_id).order_by(CatalogVersion.number.desc())
    )
    return [_version_out(v, name) for v, name in rows]


@router.get("/versions/{version_id}/categories", response_model=CategoriesOut)
async def list_categories(version_id: uuid.UUID, _user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> CategoriesOut:
    """The categories and subcategories of a version, with their number of SNS."""
    await _version(db, version_id)
    counts = dict(
        (
            await db.execute(
                select(SubcategorySns.subcategory_code, func.count(distinct(SubcategorySns.sns)))
                .where(SubcategorySns.version_id == version_id, SubcategorySns.subcategory_code.is_not(None))
                .group_by(SubcategorySns.subcategory_code)
            )
        ).all()
    )
    subs = (await db.execute(select(MaterialSubcategory).where(MaterialSubcategory.code.in_(list(counts))).order_by(MaterialSubcategory.code))).scalars().all()
    cats = {c.code: c for c in (await db.execute(select(MaterialCategory).where(MaterialCategory.code.in_({s.category_code for s in subs})))).scalars()}
    out = [
        CategoryOut(
            code=code,
            name=cats[code].name,
            subcategories=[SubcategoryOut(code=s.code, sub_code=s.sub_code, name=s.name, sns_count=counts[s.code]) for s in subs if s.category_code == code],
        )
        for code in sorted(cats)
    ]
    uncategorized = (
        await db.execute(select(func.count()).where(SubcategorySns.version_id == version_id, SubcategorySns.subcategory_code.is_(None)))
    ).scalar()
    return CategoriesOut(categories=out, uncategorized_rows=uncategorized)


@router.get("/versions/{version_id}/tree", response_model=list[TreeNode])
async def tree_level(
    version_id: uuid.UUID,
    subcategory: str = Query(min_length=4, max_length=4),
    parent: str | None = Query(default=None, min_length=6, max_length=6),
    _user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TreeNode]:
    """One level of a subcategory's tree: its roots (no parent, or a parent
    that is not in the subcategory), or the children of `parent`."""
    await _version(db, version_id)
    members = set(
        (
            await db.execute(
                select(SubcategorySns.sns).where(SubcategorySns.version_id == version_id, SubcategorySns.subcategory_code == subcategory)
            )
        ).scalars()
    )
    return [
        TreeNode(sns=n.sns, name=n.name, level=n.level, description_pending=n.description_pending, child_count=count)
        for n, count in await level_of_tree(db, version_id, members, parent)
    ]


async def _subcategories_of(db: AsyncSession, version_id: uuid.UUID, sns: list[str]) -> dict[str, list[str]]:
    out: dict[str, set[str]] = {}
    if sns:
        for code, sub in await db.execute(
            select(SubcategorySns.sns, SubcategorySns.subcategory_code).where(
                SubcategorySns.version_id == version_id, SubcategorySns.sns.in_(sns), SubcategorySns.subcategory_code.is_not(None)
            )
        ):
            out.setdefault(code, set()).add(sub)
    return {k: sorted(v) for k, v in out.items()}


@router.get("/versions/{version_id}/search", response_model=SearchPage)
async def search(
    version_id: uuid.UUID,
    q: str = Query(min_length=1, max_length=200),
    page: int = Query(default=1, ge=1),
    page_size: int | None = Query(default=None, ge=1),
    _user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> SearchPage:
    """SNS of the version by code (from its start) or by any of its names
    or its description (anywhere), any case."""
    await _version(db, version_id)
    size = await catalog_page_size(db, page_size)
    text = q.strip()
    by_extra = select(SnsExtraName.sns).where(SnsExtraName.version_id == version_id, SnsExtraName.name.ilike(f"%{like_text(text)}%", escape="\\"))
    where = (
        SnsPosition.version_id == version_id,
        or_(
            SnsPosition.sns.ilike(f"{like_text(text)}%", escape="\\"),
            SnsPosition.name.ilike(f"%{like_text(text)}%", escape="\\"),
            SnsPosition.description.ilike(f"%{like_text(text)}%", escape="\\"),
            SnsPosition.sns.in_(by_extra),
        ),
    )
    total = (await db.execute(select(func.count()).select_from(SnsPosition).where(*where))).scalar()
    hits = (await db.execute(select(SnsPosition).where(*where).order_by(SnsPosition.sns).offset((page - 1) * size).limit(size))).scalars().all()
    subs = await _subcategories_of(db, version_id, [h.sns for h in hits])
    return SearchPage(
        total=total, page=page, page_size=size,
        items=[SearchHit(sns=h.sns, name=h.name, level=h.level, description_pending=h.description_pending, subcategories=subs.get(h.sns, [])) for h in hits],
    )


@router.get("/versions/{version_id}/sns/{sns}", response_model=SnsDetail)
async def sns_detail(version_id: uuid.UUID, sns: str, _user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> SnsDetail:
    await _version(db, version_id)
    code = sns.strip().upper()
    position = (await db.execute(select(SnsPosition).where(SnsPosition.version_id == version_id, SnsPosition.sns == code))).scalar_one_or_none()
    if position is None:
        raise _not_found("sns_not_found")
    parent = None
    if position.parent_sns:
        parent = (await db.execute(select(SnsPosition).where(SnsPosition.version_id == version_id, SnsPosition.sns == position.parent_sns))).scalar_one_or_none()
    children = (
        await db.execute(select(SnsPosition).where(SnsPosition.version_id == version_id, SnsPosition.parent_sns == code).order_by(SnsPosition.sns))
    ).scalars().all()
    extras = (
        await db.execute(select(SnsExtraName).where(SnsExtraName.version_id == version_id, SnsExtraName.sns == code).order_by(SnsExtraName.name))
    ).scalars().all()
    rows = (
        await db.execute(select(SubcategorySns).where(SubcategorySns.version_id == version_id, SubcategorySns.sns == code).order_by(SubcategorySns.row_number))
    ).scalars().all()
    return SnsDetail(
        sns=position.sns,
        name=position.name,
        description=position.description,
        description_pending=position.description_pending,
        level=position.level,
        declared_levels=position.declared_levels,
        parent_sns=position.parent_sns,
        parent=SnsLink(sns=parent.sns, name=parent.name, level=parent.level) if parent else None,
        children=[SnsLink(sns=c.sns, name=c.name, level=c.level) for c in children],
        extra_names=[ExtraName(name=e.name, origin=e.origin) for e in extras],
        appearances=[
            SnsAppearance(
                subcategory_code=r.subcategory_code, subcategory_name=r.subcategory_name, category_name=r.category_name,
                declared_level=r.declared_level, name=r.name, row_number=r.row_number,
            )
            for r in rows
        ],
    )


@router.get("/versions/{version_id}/warnings", response_model=WarningsOut)
async def version_warnings(version_id: uuid.UUID, _user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> WarningsOut:
    """The CN-001..CN-006 warnings the version was imported with."""
    version = await _version(db, version_id)
    items = [w for w in version.warnings if w["code"] in WARNING_CODES]
    return WarningsOut(counts={code: sum(1 for w in items if w["code"] == code) for code in WARNING_CODES}, items=items)


@router.get("/versions/{version_id}/export")
async def export_version(
    version_id: uuid.UUID,
    subcategory: str | None = Query(default=None, min_length=4, max_length=4),
    _user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """The version (or one subcategory) in the CONF_FUN format."""
    version = await _version(db, version_id)
    if subcategory and await db.get(MaterialSubcategory, subcategory) is None:
        raise _not_found("subcategory_not_found")
    # openpyxl on thousands of rows: off the event loop.
    data = await asyncio.to_thread(write_workbook, TEMPLATE, await export_rows(db, version_id, subcategory))
    name = f"CONF_FUN_v{version.number}{'_' + subcategory if subcategory else ''}.xlsx"
    return Response(content=data, media_type=XLSX, headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.post("/import", response_model=ImportJobOut, status_code=status.HTTP_202_ACCEPTED)
async def import_version(
    background: BackgroundTasks, file: UploadFile = File(...), admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
) -> ImportJobOut:
    """Phase 1: analysed in the background against the active version; poll
    GET /api/import-jobs/{id}, then apply it to create the new version."""
    data = await import_jobs.read_upload(file, await import_jobs.limits(db))
    job = await import_jobs.start(db, target=get_target(KIND), params={}, user=admin, file_name=file.filename, data=data)
    background.add_task(import_jobs.run_analysis, job.id)
    return job_out(job)


@router.get("/diff", response_model=DiffOut)
async def diff_versions(
    from_version: uuid.UUID,
    to_version: uuid.UUID,
    change: str | None = Query(default=None, pattern="^(new|modified|removed)$"),
    page: int = Query(default=1, ge=1),
    page_size: int | None = Query(default=None, ge=1),
    _user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> DiffOut:
    """What changed from one version to another, SNS by SNS: the summary
    and a page of the detail (one kind of change, or all)."""
    await _version(db, from_version)
    await _version(db, to_version)
    size = await catalog_page_size(db, page_size)
    old, new = await comparable_positions(db, from_version), await comparable_positions(db, to_version)
    diff = compare(old, new)
    items = [
        DiffItem(sns=d["sns"], change=kind, changes=d.get("changes", []), name=(new.get(d["sns"]) or old[d["sns"]])["name"])
        for kind in _CHANGES
        if change in (None, kind)
        for d in diff[kind]
    ]
    items.sort(key=lambda i: i.sns)
    return DiffOut(
        summary={kind: len(diff[kind]) for kind in (*_CHANGES, "unchanged")},
        total=len(items),
        page=page,
        page_size=size,
        items=items[(page - 1) * size : page * size],
    )
