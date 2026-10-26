"""The CUF side of a material (E11): its subcategories, its catalog
version (with the impact of changing it), its normalized configuration
(computed: tree, figures, search, export), and "Crear CUF a partir de
otro". Reading needs material.ver; the subcategories, material.editar (the
analyst of the material, or an admin); the catalog version and the copy,
an admin."""

import asyncio
import uuid
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, require_admin, require_material_permission
from app.api.routes.catalog import XLSX, catalog_page_size, like_text
from app.api.routes.materials import _active_material, _noc_in_use, _noc_taken, _out
from app.api.routes.users import confirmation_required, version_conflict
from app.core.errors import error_detail
from app.db.base import get_db
from app.io_excel.writer import write_workbook
from app.models import CatalogVersion, Material, MaterialCategory, MaterialSubcategory, SnsExtraName, SnsPosition, User, UserMaterialRole
from app.schemas.cuf import (
    CatalogVersionChange,
    CopyIn,
    CufOut,
    CufSubcategory,
    ImpactOut,
    MaterialLink,
    NormalizedNode,
    NormalizedSearchPage,
    SubcategoriesIn,
    VersionBrief,
)
from app.schemas.materials import MaterialOut
from app.services import audit, cuf
from app.services.catalog_import import TEMPLATE, export_rows
from app.services.catalog_tree import tree_level
from app.services.permissions import MaterialAccess, accessible_materials, material_access
from app.services.snapshots import client_ip, material_snapshot

router = APIRouter(prefix="/api/materials", tags=["cuf"])


def _unprocessable(code: str, **params) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=error_detail(code, **params))


async def cuf_out(db: AsyncSession, material: Material, user: User) -> CufOut:
    version = await db.get(CatalogVersion, material.catalog_version_id) if material.catalog_version_id else None
    codes = await cuf.subcategory_codes(db, material.id)
    by_sub = await cuf.sns_by_subcategory(db, version.id, codes) if version and codes else {}
    config = cuf.union(by_sub)
    subs = (await db.execute(select(MaterialSubcategory).where(MaterialSubcategory.code.in_(codes)))).scalars().all() if codes else []
    categories = dict((await db.execute(select(MaterialCategory.code, MaterialCategory.name))).all())
    levels: Counter[str] = Counter()
    if config:
        levels.update((await db.execute(select(SnsPosition.level).where(SnsPosition.version_id == version.id, SnsPosition.sns.in_(list(config))))).scalars())
    visible = {a.material.id for a in await accessible_materials(db, user)}
    source = await db.get(Material, material.copied_from_material_id) if material.copied_from_material_id else None
    variants = (
        await db.execute(select(Material).where(Material.copied_from_material_id == material.id, Material.deleted_at.is_(None)).order_by(Material.name))
    ).scalars().all()
    return CufOut(
        material_id=material.id,
        version=material.version,
        catalog_version=VersionBrief(id=version.id, number=version.number, label=version.label, is_active=version.is_active) if version else None,
        subcategories=[
            CufSubcategory(code=s.code, name=s.name, category_code=s.category_code, category_name=categories.get(s.category_code, ""), sns_count=len(by_sub.get(s.code, ())))
            for s in sorted(subs, key=lambda s: s.code)
        ],
        sns_count=len(config),
        levels=dict(levels),
        copied_from=MaterialLink(id=source.id, name=source.name) if source and source.deleted_at is None and source.id in visible else None,
        variants=[MaterialLink(id=v.id, name=v.name) for v in variants if v.id in visible],
    )


@router.get("/{material_id}/cuf", response_model=CufOut)
async def get_cuf(
    access: MaterialAccess = Depends(require_material_permission("material.ver")),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> CufOut:
    return await cuf_out(db, access.material, user)


@router.put("/{material_id}/subcategories", response_model=CufOut)
async def set_subcategories(
    material_id: uuid.UUID,
    body: SubcategoriesIn,
    request: Request,
    _access: MaterialAccess = Depends(require_material_permission("material.editar")),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> CufOut:
    """The CUF's subcategories, all at once. Only subcategories with SNS in
    the CUF's catalog version; removing one asks the removal guards first."""
    material = await _active_material(db, material_id)
    if material.version != body.version:
        raise version_conflict(material.version)
    if material.catalog_version_id is None:
        raise _unprocessable("material_without_catalog")
    wanted = set(body.codes)
    available = set(await cuf.sns_by_subcategory(db, material.catalog_version_id, sorted(wanted))) if wanted else set()
    if wanted - available:
        raise _unprocessable("subcategory_not_in_version", codes=", ".join(sorted(wanted - available)))
    before = set(await cuf.subcategory_codes(db, material.id))
    if wanted != before:
        problem = await cuf.removal_problem(db, material, before - wanted)
        if problem:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_detail(problem[0], **problem[1]))
        await cuf.set_subcategories(db, material, wanted)
        material.version += 1
        audit.record(
            db, action="material.subcategories_changed", entity_type="material", entity_id=str(material.id),
            user_id=user.id, material_id=material.id, before={"subcategories": sorted(before)},
            after={"subcategories": sorted(wanted), "added": sorted(wanted - before), "removed": sorted(before - wanted)}, ip=client_ip(request),
        )
        await db.commit()
    return await cuf_out(db, material, user)


async def _live_version(db: AsyncSession, version_id: uuid.UUID, lock: bool = False) -> CatalogVersion | None:
    """A catalog version that is not deleted (E12)."""
    query = select(CatalogVersion).where(CatalogVersion.id == version_id, CatalogVersion.deleted_at.is_(None))
    return (await db.execute(query.with_for_update() if lock else query)).scalar_one_or_none()


@router.get("/{material_id}/catalog-version-impact", response_model=ImpactOut)
async def catalog_version_impact(
    material_id: uuid.UUID, to: uuid.UUID, _admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
) -> ImpactOut:
    material = await _active_material(db, material_id)
    if await _live_version(db, to) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_detail("catalog_version_not_found"))
    return ImpactOut(**await cuf.impact(db, material, to))


@router.put("/{material_id}/catalog-version", response_model=CufOut)
async def change_catalog_version(
    material_id: uuid.UUID, body: CatalogVersionChange, request: Request, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
) -> CufOut:
    """Only with confirm=true, after seeing the impact. The CUF's
    subcategories the new version does not have leave it (they are in the
    impact and in the audit row)."""
    if not body.confirm:
        raise confirmation_required()
    material = await _active_material(db, material_id)
    if material.version != body.version:
        raise version_conflict(material.version)
    # Locked: a version being deleted meanwhile waits, then sees this CUF.
    if await _live_version(db, body.catalog_version_id, lock=True) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_detail("catalog_version_not_found"))
    if body.catalog_version_id != material.catalog_version_id:
        report = await cuf.impact(db, material, body.catalog_version_id)
        codes = set(await cuf.subcategory_codes(db, material.id))
        if report["subcategories_missing"]:
            problem = await cuf.removal_problem(db, material, set(report["subcategories_missing"]))
            if problem:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_detail(problem[0], **problem[1]))
            await cuf.set_subcategories(db, material, codes - set(report["subcategories_missing"]))
        before = str(material.catalog_version_id) if material.catalog_version_id else None
        material.catalog_version_id = body.catalog_version_id
        material.version += 1
        audit.record(
            db, action="material.catalog_version_changed", entity_type="material", entity_id=str(material.id),
            user_id=admin.id, material_id=material.id, before={"catalog_version_id": before},
            after={"catalog_version_id": str(body.catalog_version_id), **report}, ip=client_ip(request),
        )
        await db.commit()
    return await cuf_out(db, material, admin)


async def _config(db: AsyncSession, access: MaterialAccess) -> tuple[Material, dict[str, list[str]]]:
    return access.material, await cuf.normalized_config(db, access.material)


@router.get("/{material_id}/normalized-config/tree", response_model=list[NormalizedNode])
async def normalized_tree(
    parent: str | None = Query(default=None, min_length=6, max_length=6),
    access: MaterialAccess = Depends(require_material_permission("material.ver")),
    db: AsyncSession = Depends(get_db),
) -> list[NormalizedNode]:
    """One level of the CUF's tree, each SNS with its subcategories of origin."""
    material, config = await _config(db, access)
    if not config:
        return []
    return [
        NormalizedNode(sns=n.sns, name=n.name, level=n.level, description_pending=n.description_pending, child_count=count, origins=config[n.sns])
        for n, count in await tree_level(db, material.catalog_version_id, set(config), parent)
    ]


@router.get("/{material_id}/normalized-config/search", response_model=NormalizedSearchPage)
async def normalized_search(
    q: str = Query(min_length=1, max_length=200),
    page: int = Query(default=1, ge=1),
    page_size: int | None = Query(default=None, ge=1),
    access: MaterialAccess = Depends(require_material_permission("material.ver")),
    db: AsyncSession = Depends(get_db),
) -> NormalizedSearchPage:
    material, config = await _config(db, access)
    size = await catalog_page_size(db, page_size)
    if not config:
        return NormalizedSearchPage(total=0, page=page, page_size=size, items=[])
    text = like_text(q.strip())
    version_id = material.catalog_version_id
    by_extra = select(SnsExtraName.sns).where(SnsExtraName.version_id == version_id, SnsExtraName.name.ilike(f"%{text}%", escape="\\"))
    where = (
        SnsPosition.version_id == version_id,
        SnsPosition.sns.in_(list(config)),
        or_(
            SnsPosition.sns.ilike(f"{text}%", escape="\\"),
            SnsPosition.name.ilike(f"%{text}%", escape="\\"),
            SnsPosition.description.ilike(f"%{text}%", escape="\\"),
            SnsPosition.sns.in_(by_extra),
        ),
    )
    total = (await db.execute(select(func.count()).select_from(SnsPosition).where(*where))).scalar()
    hits = (await db.execute(select(SnsPosition).where(*where).order_by(SnsPosition.sns).offset((page - 1) * size).limit(size))).scalars().all()
    return NormalizedSearchPage(
        total=total, page=page, page_size=size,
        items=[NormalizedNode(sns=h.sns, name=h.name, level=h.level, description_pending=h.description_pending, child_count=0, origins=config[h.sns]) for h in hits],
    )


@router.get("/{material_id}/normalized-config/export")
async def normalized_export(
    access: MaterialAccess = Depends(require_material_permission("material.ver")), db: AsyncSession = Depends(get_db)
) -> Response:
    """The rows of the CUF's subcategories in its catalog version, in the
    CONF_FUN format (Anexo II)."""
    material = access.material
    codes = await cuf.subcategory_codes(db, material.id)
    rows = []
    if material.catalog_version_id and codes:
        rows = [r for code in codes for r in await export_rows(db, material.catalog_version_id, code)]
    data = await asyncio.to_thread(write_workbook, TEMPLATE, rows)
    name = f"CONF_FUN_{material.noc or material.id}.xlsx"
    return Response(content=data, media_type=XLSX, headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.post("/{material_id}/copy", response_model=MaterialOut, status_code=status.HTTP_201_CREATED)
async def copy_material(
    material_id: uuid.UUID, body: CopyIn, request: Request, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
) -> MaterialOut:
    """A new CUF from another one (a variant): its own name and identifiers;
    the description, Grupo-Clase, catalog version and everything the
    registered copiers copy (subcategories; the members if asked). It keeps
    `copied_from` and is independent of the original from then on."""
    source = await _active_material(db, material_id)
    if await _noc_in_use(db, body.noc):
        raise _noc_taken()
    target = Material(
        name=body.name, noc=body.noc, part_number=body.part_number, ncage=body.ncage, description=source.description,
        grupo_clase=source.grupo_clase, catalog_version_id=source.catalog_version_id, copied_from_material_id=source.id, version=1,
    )
    db.add(target)
    try:
        await db.flush()
    except IntegrityError:
        raise _noc_taken() from None
    options = cuf.CopyOptions(copy_members=body.copy_members)
    for _name, copier in cuf.MATERIAL_COPIERS:
        await copier(db, source, target, options)
    # Who got access to the new CUF, and with which role (D11).
    members = (await db.execute(select(UserMaterialRole).where(UserMaterialRole.material_id == target.id))).scalars().all()
    audit.record(
        db, action="material.copied", entity_type="material", entity_id=str(target.id), user_id=admin.id, material_id=target.id,
        before={"from": str(source.id), "from_name": source.name},
        after={**material_snapshot(target), "copiers": [name for name, _fn in cuf.MATERIAL_COPIERS], "copy_members": body.copy_members,
               "members": sorted([{"user_id": str(m.user_id), "role": m.role_code} for m in members], key=lambda m: m["user_id"])},
        ip=client_ip(request),
    )
    await db.commit()
    await db.refresh(target)
    return _out(await material_access(db, admin, target.id))
