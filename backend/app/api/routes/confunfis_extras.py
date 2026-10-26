"""The rest of RF-02 in a CUF (E14): its "Tabla de partes" (read: the parts
are the article's, edited under /api/articles/{id}/parts), its functional
products, and the extra functions and incompatibilities of its CONFUNFIS
rows. Reading needs confunfis.ver, writing confunfis.editar (D5); every
change goes with its version and is audited.
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, require_material_permission
from app.api.routes.confunfis import EDIT, READ, Context, _context, _serialized, article_brief, cuf_parts, extra_out, incompatibility_out
from app.api.routes.users import confirmation_required, version_conflict
from app.core.errors import error_detail
from app.db.base import get_db
from app.models import Article, ExtraFunction, FunctionalProduct, Incompatibility, Material, ReferenceValue, User
from app.schemas.confunfis_extras import (
    CufPartOut,
    ExtraFunctionIn,
    ExtraFunctionOut,
    ExtraFunctionUpdate,
    IncompatibilityIn,
    IncompatibilityOut,
    IncompatibilityUpdate,
    ProductIn,
    ProductOut,
    ProductUpdate,
)
from app.services import audit, confunfis
from app.services import confunfis_extras as extras
from app.services.permissions import MaterialAccess
from app.services.snapshots import client_ip

router = APIRouter(prefix="/api/materials/{material_id}/confunfis", tags=["confunfis"])


def _invalid(exc: extras.ExtraError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=error_detail("confunfis_extra_invalid", problems=exc.problems))


def _not_found(code: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_detail(code))


async def _refresh(db: AsyncSession, material: Material) -> None:
    await extras.refresh_products(db, material)
    await confunfis.refresh_observations(db, material)


async def _locked(db: AsyncSession, model: Any, material: Material, item_id: uuid.UUID, version: int, missing: str) -> Any:
    await _serialized(db, material)
    item = (
        await db.execute(select(model).where(model.id == item_id, model.material_id == material.id, model.deleted_at.is_(None)).with_for_update())
    ).scalar_one_or_none()
    if item is None:
        raise _not_found(missing)
    if item.version != version:
        raise version_conflict(item.version)
    return item


# ── the CUF's parts table ────────────────────────────────────────────────


@router.get("/parts", response_model=list[CufPartOut])
async def parts_of_cuf(access: MaterialAccess = Depends(require_material_permission(READ)), user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> list[CufPartOut]:
    """The parts of every article in the CUF's CONFUNFIS, with their total in it."""
    return await cuf_parts(db, await _context(db, access.material, user))


# ── functional products ──────────────────────────────────────────────────


async def _products_out(db: AsyncSession, products: list[FunctionalProduct]) -> list[ProductOut]:
    codes = {p.pol_code for p in products if p.pol_code}
    descriptions = dict(
        (await db.execute(select(ReferenceValue.code, ReferenceValue.description).where(ReferenceValue.table_code == "POL", ReferenceValue.code.in_(codes)))).all()
    ) if codes else {}
    ids = {p.article_id for p in products if p.article_id}
    articles = {a.id: a for a in (await db.execute(select(Article).where(Article.id.in_(ids)))).scalars()} if ids else {}
    return [
        ProductOut(
            id=p.id, designation=p.designation, pol_code=p.pol_code, pol_description=descriptions.get(p.pol_code) if p.pol_code else None, nae=p.nae, noc=p.noc,
            article=article_brief(articles.get(p.article_id) if p.article_id else None, None), supply_unit=p.supply_unit,
            quantity=None if p.quantity is None else str(p.quantity), unit=p.unit, source=p.source, observations=p.observations,
            observation_codes=list(p.observation_codes), version=p.version, updated_at=p.updated_at,
        )
        for p in products
    ]


async def _product_done(db: AsyncSession, material: Material, product_id: uuid.UUID) -> ProductOut:
    await _refresh(db, material)
    await db.commit()
    product = await db.get(FunctionalProduct, product_id)
    assert product is not None
    await db.refresh(product)
    return (await _products_out(db, [product]))[0]


@router.get("/products", response_model=list[ProductOut])
async def list_products(access: MaterialAccess = Depends(require_material_permission(READ)), db: AsyncSession = Depends(get_db)) -> list[ProductOut]:
    return await _products_out(db, await extras.live_products(db, access.material.id))


@router.post("/products", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
async def create_product(
    body: ProductIn, request: Request, access: MaterialAccess = Depends(require_material_permission(EDIT)),
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
) -> ProductOut:
    await _serialized(db, access.material)
    try:
        product = await extras.save_product(db, access.material, body.model_dump(), user.id, source="manual", ip=client_ip(request))
    except extras.ExtraError as exc:
        raise _invalid(exc) from None
    return await _product_done(db, access.material, product.id)


@router.patch("/products/{product_id}", response_model=ProductOut)
async def update_product(
    product_id: uuid.UUID, body: ProductUpdate, request: Request, access: MaterialAccess = Depends(require_material_permission(EDIT)),
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
) -> ProductOut:
    product = await _locked(db, FunctionalProduct, access.material, product_id, body.version, "functional_product_not_found")
    values = {**extras.snapshot(product, extras.PRODUCT_FIELDS), **{k: getattr(body, k) for k in body.model_fields_set - {"version"}}}
    try:
        await extras.save_product(db, access.material, values, user.id, source=product.source, product=product, ip=client_ip(request))
    except extras.ExtraError as exc:
        raise _invalid(exc) from None
    return await _product_done(db, access.material, product.id)


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: uuid.UUID, version: int, request: Request, confirm: bool = False,
    access: MaterialAccess = Depends(require_material_permission(EDIT)), user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
) -> None:
    if not confirm:
        raise confirmation_required()
    product = await _locked(db, FunctionalProduct, access.material, product_id, version, "functional_product_not_found")
    await extras.remove_product(db, access.material, product, user.id, client_ip(request))
    await _refresh(db, access.material)
    await db.commit()


# ── extra functions ──────────────────────────────────────────────────────


def _live_row(ctx: Context, row_id: uuid.UUID) -> Any:
    """A live row of this CUF; another CUF's (or a removed one) is a 422."""
    row = next((r for r in ctx.rows if r.id == row_id), None)
    if row is None:
        raise _invalid(extras.ExtraError([{"field": "position_id", "code": "row_not_found", "params": {}}]))
    return row


async def _extra_done(db: AsyncSession, access: MaterialAccess, user: User, extra_id: uuid.UUID) -> ExtraFunctionOut:
    await _refresh(db, access.material)
    await db.commit()
    ctx = await _context(db, access.material, user)
    return extra_out(ctx, next(e for e in ctx.extras if e.id == extra_id))


@router.get("/extra-functions", response_model=list[ExtraFunctionOut])
async def list_extra_functions(
    access: MaterialAccess = Depends(require_material_permission(READ)), user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
) -> list[ExtraFunctionOut]:
    ctx = await _context(db, access.material, user)
    return [extra_out(ctx, e) for e in ctx.extras]


@router.post("/extra-functions", response_model=ExtraFunctionOut, status_code=status.HTTP_201_CREATED)
async def create_extra_function(
    body: ExtraFunctionIn, request: Request, access: MaterialAccess = Depends(require_material_permission(EDIT)),
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
) -> ExtraFunctionOut:
    material = access.material
    await _serialized(db, material)
    row = _live_row(await _context(db, material, user), body.position_id)
    sns, criterion = body.sns.strip().upper(), body.criterion.strip()
    problems = await extras.check_extra(db, material, row, sns, criterion)
    if problems:
        raise _invalid(extras.ExtraError(problems))
    extra = await extras.add_extra(db, material, row, sns, criterion, body.comment, user.id, ip=client_ip(request))
    return await _extra_done(db, access, user, extra.id)


@router.patch("/extra-functions/{extra_id}", response_model=ExtraFunctionOut)
async def update_extra_function(
    extra_id: uuid.UUID, body: ExtraFunctionUpdate, request: Request, access: MaterialAccess = Depends(require_material_permission(EDIT)),
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
) -> ExtraFunctionOut:
    material = access.material
    extra = await _locked(db, ExtraFunction, material, extra_id, body.version, "extra_function_not_found")
    row = _live_row(await _context(db, material, user), extra.position_id)
    sent = body.model_fields_set
    sns = body.sns.strip().upper() if "sns" in sent and body.sns else extra.sns
    criterion = body.criterion.strip() if "criterion" in sent and body.criterion else extra.criterion
    problems = await extras.check_extra(db, material, row, sns, criterion, current=extra)
    if problems:
        raise _invalid(extras.ExtraError(problems))
    before = extras.extra_snapshot(extra)
    extra.sns, extra.criterion = sns, criterion
    if "comment" in sent:
        extra.comment = (body.comment or "").strip() or None
    extra.version, extra.updated_by = extra.version + 1, user.id
    audit.record(db, action="confunfis.extra_function_updated", entity_type="extra_function", entity_id=str(extra.id), user_id=user.id, material_id=material.id, before=before, after=extras.extra_snapshot(extra), ip=client_ip(request))
    return await _extra_done(db, access, user, extra.id)


@router.delete("/extra-functions/{extra_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_extra_function(
    extra_id: uuid.UUID, version: int, request: Request, confirm: bool = False,
    access: MaterialAccess = Depends(require_material_permission(EDIT)), user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
) -> None:
    if not confirm:
        raise confirmation_required()
    extra = await _locked(db, ExtraFunction, access.material, extra_id, version, "extra_function_not_found")
    await extras.remove_extra(db, access.material, extra, user.id, client_ip(request))
    await _refresh(db, access.material)
    await db.commit()


# ── incompatibilities ────────────────────────────────────────────────────


async def _incompatibility_done(db: AsyncSession, access: MaterialAccess, user: User, item_id: uuid.UUID) -> IncompatibilityOut:
    await _refresh(db, access.material)
    await db.commit()
    ctx = await _context(db, access.material, user)
    return incompatibility_out(ctx, next(i for i in ctx.incompatibilities if i.id == item_id))


def _repeated(ctx: Context, a: uuid.UUID, b: uuid.UUID, kind: str, current: Incompatibility | None = None) -> None:
    if any(extras.same_incompatibility(i, a, b, kind) and i is not current for i in ctx.incompatibilities):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_detail("incompatibility_exists"))


@router.get("/incompatibilities", response_model=list[IncompatibilityOut])
async def list_incompatibilities(
    access: MaterialAccess = Depends(require_material_permission(READ)), user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
) -> list[IncompatibilityOut]:
    ctx = await _context(db, access.material, user)
    return [incompatibility_out(ctx, i) for i in ctx.incompatibilities]


@router.post("/incompatibilities", response_model=IncompatibilityOut, status_code=status.HTTP_201_CREATED)
async def create_incompatibility(
    body: IncompatibilityIn, request: Request, access: MaterialAccess = Depends(require_material_permission(EDIT)),
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
) -> IncompatibilityOut:
    material = access.material
    await _serialized(db, material)
    if body.row_a_id == body.row_b_id:
        raise _invalid(extras.ExtraError([{"field": "row_b_id", "code": "same_row", "params": {}}]))
    ctx = await _context(db, material, user)
    a, b = _live_row(ctx, body.row_a_id), _live_row(ctx, body.row_b_id)
    _repeated(ctx, a.id, b.id, body.kind)
    reason = body.reason.strip()
    if not reason:
        raise _invalid(extras.ExtraError([{"field": "reason", "code": "required", "params": {}}]))
    item = await extras.add_incompatibility(db, material, a, b, body.kind, reason, user.id, ip=client_ip(request))
    return await _incompatibility_done(db, access, user, item.id)


@router.patch("/incompatibilities/{item_id}", response_model=IncompatibilityOut)
async def update_incompatibility(
    item_id: uuid.UUID, body: IncompatibilityUpdate, request: Request, access: MaterialAccess = Depends(require_material_permission(EDIT)),
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
) -> IncompatibilityOut:
    material = access.material
    item = await _locked(db, Incompatibility, material, item_id, body.version, "incompatibility_not_found")
    sent = body.model_fields_set
    kind = body.kind if "kind" in sent and body.kind else item.kind
    reason = body.reason.strip() if "reason" in sent and body.reason else item.reason
    if not reason:
        raise _invalid(extras.ExtraError([{"field": "reason", "code": "required", "params": {}}]))
    _repeated(await _context(db, material, user), item.row_a_id, item.row_b_id, kind, current=item)
    before = extras.incompatibility_snapshot(item)
    item.kind, item.reason, item.version, item.updated_by = kind, reason, item.version + 1, user.id
    audit.record(db, action="confunfis.incompatibility_updated", entity_type="incompatibility", entity_id=str(item.id), user_id=user.id, material_id=material.id, before=before, after=extras.incompatibility_snapshot(item), ip=client_ip(request))
    return await _incompatibility_done(db, access, user, item.id)


@router.delete("/incompatibilities/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_incompatibility(
    item_id: uuid.UUID, version: int, request: Request, confirm: bool = False,
    access: MaterialAccess = Depends(require_material_permission(EDIT)), user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
) -> None:
    if not confirm:
        raise confirmation_required()
    item = await _locked(db, Incompatibility, access.material, item_id, version, "incompatibility_not_found")
    await extras.remove_incompatibility(db, access.material, item, user.id, client_ip(request))
    await _refresh(db, access.material)
    await db.commit()
