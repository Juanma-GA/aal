"""Materials (= CUF, D12) and who works on each.

- Every user lists only the materials they are assigned to (an admin, all),
  each with their role and permissions on it.
- GET /{material_id} needs material.ver on it; a material the user is not
  in is a 404 (require_material_permission).
- Its team (members) and recent activity: material.ver on it.
- Creating, editing and deleting a material, and assigning its members,
  are admin only. Edits carry the version they read (D10); a delete or the removal of
  a member needs ?confirm=true (HR9).
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, material_not_found, require_admin, require_material_permission
from app.api.routes.users import confirmation_required, user_not_found, version_conflict
from app.core.errors import error_detail
from app.db.base import get_db
from app.models import AuditLog, Material, Role, User, UserMaterialRole
from app.schemas.materials import ActivityEntry, MaterialCreate, MaterialOut, MaterialUpdate, MemberAssign, MemberOut
from app.services import audit
from app.services.parameters import get_parameter
from app.services.permissions import MaterialAccess, accessible_materials, material_access
from app.services.snapshots import client_ip, material_snapshot

router = APIRouter(prefix="/api/materials", tags=["materials"])


def _out(access: MaterialAccess) -> MaterialOut:
    m = access.material
    return MaterialOut(
        id=m.id,
        noc=m.noc,
        name=m.name,
        part_number=m.part_number,
        ncage=m.ncage,
        description=m.description,
        created_at=m.created_at,
        updated_at=m.updated_at,
        version=m.version,
        role=access.role,
        permissions=sorted(access.permissions),
    )


def _noc_taken() -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_detail("material_noc_taken"))


async def _noc_in_use(db: AsyncSession, noc: str | None, exclude: uuid.UUID | None = None) -> bool:
    if noc is None:
        return False
    query = select(Material.id).where(Material.noc == noc, Material.deleted_at.is_(None))
    if exclude is not None:
        query = query.where(Material.id != exclude)
    return (await db.execute(query)).first() is not None


async def _active_material(db: AsyncSession, material_id: uuid.UUID) -> Material:
    material = (
        await db.execute(select(Material).where(Material.id == material_id, Material.deleted_at.is_(None)).with_for_update())
    ).scalar_one_or_none()
    if material is None:
        raise material_not_found()
    return material


@router.get("", response_model=list[MaterialOut])
async def list_materials(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> list[MaterialOut]:
    return [_out(a) for a in await accessible_materials(db, user)]


@router.post("", response_model=MaterialOut, status_code=status.HTTP_201_CREATED)
async def create_material(
    body: MaterialCreate, request: Request, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
) -> MaterialOut:
    if await _noc_in_use(db, body.noc):
        raise _noc_taken()
    material = Material(**body.model_dump(), version=1)
    db.add(material)
    try:
        await db.flush()
    except IntegrityError:
        raise _noc_taken() from None
    audit.record(
        db,
        action="material.created",
        entity_type="material",
        entity_id=str(material.id),
        user_id=admin.id,
        material_id=material.id,
        after=material_snapshot(material),
        ip=client_ip(request),
    )
    await db.commit()
    await db.refresh(material)
    return _out(await material_access(db, admin, material.id))


@router.get("/{material_id}", response_model=MaterialOut)
async def get_material(access: MaterialAccess = Depends(require_material_permission("material.ver"))) -> MaterialOut:
    return _out(access)


@router.patch("/{material_id}", response_model=MaterialOut)
async def update_material(
    material_id: uuid.UUID,
    body: MaterialUpdate,
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> MaterialOut:
    material = await _active_material(db, material_id)
    if material.version != body.version:
        raise version_conflict(material.version)
    changes = body.model_dump(exclude_unset=True, exclude={"version"})
    if "name" in changes and changes["name"] is None:
        del changes["name"]
    if "noc" in changes and await _noc_in_use(db, changes["noc"], exclude=material.id):
        raise _noc_taken()
    before = material_snapshot(material)
    for field, value in changes.items():
        setattr(material, field, "" if field == "description" and value is None else value)
    material.version += 1
    audit.record(
        db,
        action="material.updated",
        entity_type="material",
        entity_id=str(material.id),
        user_id=admin.id,
        material_id=material.id,
        before=before,
        after=material_snapshot(material),
        ip=client_ip(request),
    )
    await db.commit()
    await db.refresh(material)  # updated_at is set by the database
    return _out(await material_access(db, admin, material.id))


@router.delete("/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_material(
    material_id: uuid.UUID,
    request: Request,
    confirm: bool = False,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft delete: it stops being visible to anyone; its members and data
    are kept."""
    if not confirm:
        raise confirmation_required()
    material = await _active_material(db, material_id)
    before = material_snapshot(material)
    material.deleted_at = datetime.now(UTC)
    material.deleted_by = admin.id
    material.version += 1
    audit.record(
        db,
        action="material.deleted",
        entity_type="material",
        entity_id=str(material.id),
        user_id=admin.id,
        material_id=material.id,
        before=before,
        after=material_snapshot(material),
        ip=client_ip(request),
    )
    await db.commit()


# ── Members ──────────────────────────────────────────────────────────────


@router.get("/{material_id}/members", response_model=list[MemberOut], response_model_exclude_none=True)
async def list_members(
    access: MaterialAccess = Depends(require_material_permission("material.ver")),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MemberOut]:
    """The material's team: anyone who may see the material sees each
    member's name and role (the Panel); only an admin also gets their id,
    email and assignment date (to manage them)."""
    rows = (
        await db.execute(
            select(UserMaterialRole, User)
            .join(User, User.id == UserMaterialRole.user_id)
            .where(UserMaterialRole.material_id == access.material.id, User.deleted_at.is_(None))
            .order_by(User.display_name, User.email)
        )
    ).all()
    if user.is_admin:
        return [
            MemberOut(user_id=u.id, email=u.email, display_name=u.display_name, role=r.role_code, assigned_at=r.assigned_at)
            for r, u in rows
        ]
    return [MemberOut(display_name=u.display_name, role=r.role_code) for r, u in rows]


@router.get("/{material_id}/activity", response_model=list[ActivityEntry])
async def material_activity(
    access: MaterialAccess = Depends(require_material_permission("material.ver")),
    db: AsyncSession = Depends(get_db),
) -> list[ActivityEntry]:
    """The latest actions recorded on this material (parameter
    panel.activity_items): who, what and when -- never the data before and
    after, which only the global audit log (admin) shows."""
    limit = (await get_parameter(db, "panel"))["activity_items"]
    rows = (
        await db.execute(
            select(AuditLog.created_at, AuditLog.action, AuditLog.entity_type, User.display_name)
            .outerjoin(User, User.id == AuditLog.user_id)
            .where(AuditLog.material_id == access.material.id)
            .order_by(AuditLog.created_at.desc(), AuditLog.id)
            .limit(limit)
        )
    ).all()
    return [ActivityEntry(created_at=c, action=a, entity_type=e, user_name=n) for c, a, e, n in rows]


def _member_audit(db, request, admin, material, user, action, before_role, after_role) -> None:
    audit.record(
        db,
        action=action,
        entity_type="user_material_role",
        entity_id=f"{user.id}:{material.id}",
        user_id=admin.id,
        material_id=material.id,
        before=None if before_role is None else {"user": user.email, "role": before_role},
        after=None if after_role is None else {"user": user.email, "role": after_role},
        ip=client_ip(request),
    )


@router.put("/{material_id}/members/{user_id}", response_model=MemberOut)
async def assign_member(
    material_id: uuid.UUID,
    user_id: uuid.UUID,
    body: MemberAssign,
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> MemberOut:
    """Assigns the role, or changes it (one role per user and material)."""
    material = await _active_material(db, material_id)
    user = (await db.execute(select(User).where(User.id == user_id, User.deleted_at.is_(None)))).scalar_one_or_none()
    if user is None:
        raise user_not_found()
    if await db.get(Role, body.role) is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=error_detail("role_unknown"))
    row = (
        await db.execute(
            select(UserMaterialRole)
            .where(UserMaterialRole.user_id == user_id, UserMaterialRole.material_id == material_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if row is None:
        row = UserMaterialRole(user_id=user_id, material_id=material_id, role_code=body.role, assigned_by=admin.id)
        db.add(row)
        _member_audit(db, request, admin, material, user, "material_role.assigned", None, body.role)
    elif row.role_code != body.role:
        previous = row.role_code
        row.role_code = body.role
        row.assigned_by = admin.id
        _member_audit(db, request, admin, material, user, "material_role.changed", previous, body.role)
    await db.commit()
    await db.refresh(row)
    return MemberOut(user_id=user.id, email=user.email, display_name=user.display_name, role=row.role_code, assigned_at=row.assigned_at)


@router.delete("/{material_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    material_id: uuid.UUID,
    user_id: uuid.UUID,
    request: Request,
    confirm: bool = False,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    if not confirm:
        raise confirmation_required()
    material = await _active_material(db, material_id)
    row = (
        await db.execute(
            select(UserMaterialRole)
            .where(UserMaterialRole.user_id == user_id, UserMaterialRole.material_id == material_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_detail("member_not_found"))
    user = await db.get(User, user_id)
    _member_audit(db, request, admin, material, user, "material_role.removed", row.role_code, None)
    await db.delete(row)
    await db.commit()
