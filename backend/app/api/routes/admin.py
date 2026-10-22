"""Read-only administration: the role matrix, the audit log and the
parameters in force."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, require_admin
from app.core.errors import error_detail
from app.db.base import get_db
from app.models import AuditLog, Material, Permission, Role, User
from app.schemas.admin import AuditEntry, AuditFacets, AuditPage, ParameterOut, PermissionOut, RoleMatrix, RoleOut
from app.services.parameters import PARAMETER_DEFAULTS, get_parameter
from app.services.permissions import role_permissions

router = APIRouter(prefix="/api", tags=["admin"])


@router.get("/roles", response_model=RoleMatrix)
async def roles(_user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> RoleMatrix:
    role_rows = (await db.execute(select(Role).order_by(Role.sort_order))).scalars().all()
    permission_rows = (await db.execute(select(Permission).order_by(Permission.sort_order))).scalars().all()
    matrix = await role_permissions(db)
    order = {p.code: p.sort_order for p in permission_rows}
    return RoleMatrix(
        roles=[RoleOut(code=r.code) for r in role_rows],
        permissions=[PermissionOut(code=p.code, area=p.area) for p in permission_rows],
        matrix={r.code: sorted(matrix.get(r.code, ()), key=order.__getitem__) for r in role_rows},
    )


@router.get("/audit", response_model=AuditPage)
async def audit_log(
    user_id: uuid.UUID | None = None,
    material_id: uuid.UUID | None = None,
    entity_type: str | None = Query(default=None, max_length=100),
    action: str | None = Query(default=None, max_length=100),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int | None = Query(default=None, ge=1),
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AuditPage:
    """Newest first. page_size over the parameter audit.max_page_size is
    refused with the limit, never lowered silently (HR7)."""
    params = await get_parameter(db, "audit")
    size = page_size or params["page_size"]
    if size > params["max_page_size"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=error_detail("page_size_too_large", max_page_size=params["max_page_size"]),
        )
    conditions = []
    if user_id is not None:
        conditions.append(AuditLog.user_id == user_id)
    if material_id is not None:
        conditions.append(AuditLog.material_id == material_id)
    if entity_type:
        conditions.append(AuditLog.entity_type == entity_type)
    if action:
        conditions.append(AuditLog.action == action)
    if date_from is not None:
        conditions.append(AuditLog.created_at >= date_from)
    if date_to is not None:
        conditions.append(AuditLog.created_at <= date_to)
    total = await db.scalar(select(func.count()).select_from(AuditLog).where(*conditions)) or 0
    rows = (
        await db.execute(
            select(AuditLog, User.email, Material.name)
            .outerjoin(User, User.id == AuditLog.user_id)
            .outerjoin(Material, Material.id == AuditLog.material_id)
            .where(*conditions)
            .order_by(AuditLog.created_at.desc(), AuditLog.id)
            .offset((page - 1) * size)
            .limit(size)
        )
    ).all()
    return AuditPage(
        items=[
            AuditEntry(
                id=a.id,
                created_at=a.created_at,
                user_id=a.user_id,
                user_email=email,
                action=a.action,
                entity_type=a.entity_type,
                entity_id=a.entity_id,
                material_id=a.material_id,
                material_name=name,
                before=a.before,
                after=a.after,
                ip=str(a.ip) if a.ip is not None else None,
            )
            for a, email, name in rows
        ],
        total=total,
        page=page,
        page_size=size,
    )


@router.get("/audit/facets", response_model=AuditFacets)
async def audit_facets(_admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)) -> AuditFacets:
    """The actions and entity types the log holds, for the filters."""
    actions = (await db.execute(select(AuditLog.action).distinct().order_by(AuditLog.action))).scalars().all()
    types = (await db.execute(select(AuditLog.entity_type).distinct().order_by(AuditLog.entity_type))).scalars().all()
    return AuditFacets(actions=list(actions), entity_types=list(types))


@router.get("/parameters", response_model=list[ParameterOut])
async def parameters(_admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)) -> list[ParameterOut]:
    """Every parameter as it is in force (defaults deep-merged with what the
    database stores)."""
    return [ParameterOut(key=key, value=await get_parameter(db, key)) for key in PARAMETER_DEFAULTS]
