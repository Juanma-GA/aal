"""User administration (admin only): list, create with a temporary
password, edit, deactivate / reactivate, soft delete (HR9) and reset the
password. Every change goes to the audit log, never a password."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.errors import error_detail
from app.core.security import generate_temporary_password, hash_password
from app.db.base import get_db
from app.models import Material, User, UserMaterialRole
from app.schemas.users import PasswordReset, UserCreate, UserCreated, UserMaterialOut, UserOut, UserUpdate
from app.services import audit, sessions
from app.services.parameters import get_parameter
from app.services.snapshots import client_ip, user_snapshot

router = APIRouter(prefix="/api/users", tags=["users"])


def user_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_detail("user_not_found"))


def version_conflict(current: int) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_detail("version_conflict", current_version=current))


def confirmation_required() -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_detail("confirmation_required"))


async def _materials_of(db: AsyncSession, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[UserMaterialOut]]:
    rows = (
        await db.execute(
            select(UserMaterialRole.user_id, Material.id, Material.name, UserMaterialRole.role_code)
            .join(Material, Material.id == UserMaterialRole.material_id)
            .where(UserMaterialRole.user_id.in_(user_ids), Material.deleted_at.is_(None))
            .order_by(Material.name)
        )
    ).all()
    out: dict[uuid.UUID, list[UserMaterialOut]] = {}
    for user_id, material_id, name, role in rows:
        out.setdefault(user_id, []).append(UserMaterialOut(material_id=material_id, material_name=name, role=role))
    return out


def _out(user: User, materials: list[UserMaterialOut] | None = None) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        is_admin=user.is_admin,
        is_active=user.is_active,
        must_change_password=user.must_change_password,
        created_at=user.created_at,
        deleted_at=user.deleted_at,
        version=user.version,
        materials=materials or [],
    )


async def _active_user(db: AsyncSession, user_id: uuid.UUID, *, for_update: bool = False) -> User:
    query = select(User).where(User.id == user_id, User.deleted_at.is_(None))
    if for_update:
        query = query.with_for_update()
    user = (await db.execute(query)).scalar_one_or_none()
    if user is None:
        raise user_not_found()
    return user


def _guard_own_access(admin: User, target: User) -> None:
    """Nobody takes away their own access (admin flag, active, account).
    This also keeps at least one active admin: whoever changes another
    admin is an active admin themselves."""
    if target.id == admin.id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_detail("cannot_change_own_access"))


@router.get("", response_model=list[UserOut])
async def list_users(
    q: str | None = Query(default=None, max_length=200),
    include_deleted: bool = False,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[UserOut]:
    query = select(User)
    if not include_deleted:
        query = query.where(User.deleted_at.is_(None))
    if q:
        pattern = f"%{q.strip().lower()}%"
        query = query.where(or_(func.lower(User.email).like(pattern), func.lower(User.display_name).like(pattern)))
    users = (await db.execute(query.order_by(User.display_name, User.email))).scalars().all()
    materials = await _materials_of(db, [u.id for u in users])
    return [_out(u, materials.get(u.id)) for u in users]


@router.post("", response_model=UserCreated, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreate, request: Request, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
) -> UserCreated:
    email = body.email.strip().lower()
    existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if existing is not None:
        code = "user_email_deleted" if existing.deleted_at is not None else "user_email_taken"
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_detail(code))
    params = await get_parameter(db, "auth")
    temporary = generate_temporary_password(params["temporary_password_length"])
    user = User(
        email=email,
        display_name=body.display_name,
        password_hash=hash_password(temporary),
        is_admin=body.is_admin,
        is_active=True,
        must_change_password=True,
        ui_preferences={},
        version=1,
    )
    db.add(user)
    await db.flush()
    audit.record(
        db, action="user.created", entity_type="user", entity_id=str(user.id), user_id=admin.id, after=user_snapshot(user), ip=client_ip(request)
    )
    await db.commit()
    await db.refresh(user)
    return UserCreated(user=_out(user), temporary_password=temporary)


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: uuid.UUID,
    body: UserUpdate,
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    user = await _active_user(db, user_id, for_update=True)
    if user.version != body.version:
        raise version_conflict(user.version)
    changes = {k: v for k, v in body.model_dump(exclude_unset=True, exclude={"version"}).items() if v is not None}
    if any(field in changes and changes[field] != getattr(user, field) for field in ("is_admin", "is_active")):
        _guard_own_access(admin, user)
    before = user_snapshot(user)
    for field in ("display_name", "is_admin", "is_active"):
        if field in changes:
            setattr(user, field, changes[field])
    action = "user.updated"
    if changes.get("is_active") is False and before["is_active"]:
        action = "user.deactivated"
        await sessions.end_user_sessions(db, user.id, "user_deactivated")
    elif changes.get("is_active") is True and not before["is_active"]:
        action = "user.reactivated"
    user.version += 1
    audit.record(
        db, action=action, entity_type="user", entity_id=str(user.id), user_id=admin.id, before=before, after=user_snapshot(user), ip=client_ip(request)
    )
    await db.commit()
    await db.refresh(user)
    return _out(user, (await _materials_of(db, [user.id])).get(user.id))


@router.post("/{user_id}/reset-password", response_model=PasswordReset)
async def reset_password(
    user_id: uuid.UUID, request: Request, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
) -> PasswordReset:
    """A new temporary password (shown once), a forced change at the next
    login, and every session of the user ended. An admin changes their own
    password at /api/me/password."""
    user = await _active_user(db, user_id, for_update=True)
    _guard_own_access(admin, user)
    params = await get_parameter(db, "auth")
    temporary = generate_temporary_password(params["temporary_password_length"])
    before = user_snapshot(user)
    user.password_hash = hash_password(temporary)
    user.must_change_password = True
    user.version += 1
    await sessions.end_user_sessions(db, user.id, "password_reset")
    audit.record(
        db,
        action="user.password_reset",
        entity_type="user",
        entity_id=str(user.id),
        user_id=admin.id,
        before=before,
        after=user_snapshot(user),
        ip=client_ip(request),
    )
    await db.commit()
    await db.refresh(user)
    return PasswordReset(user=_out(user), temporary_password=temporary)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: uuid.UUID,
    request: Request,
    confirm: bool = False,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft delete (HR9): needs ?confirm=true; the row and its history stay,
    the person can no longer sign in and their sessions end."""
    if not confirm:
        raise confirmation_required()
    user = await _active_user(db, user_id, for_update=True)
    _guard_own_access(admin, user)
    before = user_snapshot(user)
    user.deleted_at = datetime.now(UTC)
    user.deleted_by = admin.id
    user.is_active = False
    user.version += 1
    await sessions.end_user_sessions(db, user.id, "user_deleted")
    audit.record(
        db, action="user.deleted", entity_type="user", entity_id=str(user.id), user_id=admin.id, before=before, after=user_snapshot(user), ip=client_ip(request)
    )
    await db.commit()
