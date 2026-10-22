"""Who may do what on a material (D5). The database's matrix
(role_permission) is the only source: no role or permission is decided in
code. A global admin has every permission on every material."""

import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Material, Permission, RolePermission, User, UserMaterialRole


@dataclass(frozen=True)
class MaterialAccess:
    material: Material
    # The user's role on it; None for an admin without an assignment.
    role: str | None
    permissions: frozenset[str] = field(default_factory=frozenset)

    def can(self, permission: str) -> bool:
        return permission in self.permissions


async def all_permissions(db: AsyncSession) -> frozenset[str]:
    return frozenset((await db.execute(select(Permission.code))).scalars().all())


async def role_permissions(db: AsyncSession) -> dict[str, frozenset[str]]:
    rows = (await db.execute(select(RolePermission.role_code, RolePermission.permission_code))).all()
    matrix: dict[str, set[str]] = {}
    for role, permission in rows:
        matrix.setdefault(role, set()).add(permission)
    return {role: frozenset(perms) for role, perms in matrix.items()}


async def material_access(db: AsyncSession, user: User, material_id: uuid.UUID) -> MaterialAccess | None:
    """The user's access to an active material, or None when they have none
    (or it does not exist, or it is deleted): the same answer for all, so
    nobody learns which materials exist without being in them."""
    material = await db.get(Material, material_id)
    if material is None or material.deleted_at is not None:
        return None
    role = await db.scalar(
        select(UserMaterialRole.role_code).where(
            UserMaterialRole.user_id == user.id, UserMaterialRole.material_id == material_id
        )
    )
    if user.is_admin:
        return MaterialAccess(material, role, await all_permissions(db))
    if role is None:
        return None
    return MaterialAccess(material, role, (await role_permissions(db)).get(role, frozenset()))


async def accessible_materials(db: AsyncSession, user: User) -> list[MaterialAccess]:
    """Every material the user may see (an admin: all), by name."""
    query = select(Material, UserMaterialRole.role_code).outerjoin(
        UserMaterialRole, (UserMaterialRole.material_id == Material.id) & (UserMaterialRole.user_id == user.id)
    ).where(Material.deleted_at.is_(None))
    if not user.is_admin:
        query = query.where(UserMaterialRole.role_code.is_not(None))
    rows = (await db.execute(query.order_by(Material.name, Material.id))).all()
    if user.is_admin:
        everything = await all_permissions(db)
        return [MaterialAccess(m, role, everything) for m, role in rows]
    matrix = await role_permissions(db)
    return [MaterialAccess(m, role, matrix.get(role, frozenset())) for m, role in rows]
