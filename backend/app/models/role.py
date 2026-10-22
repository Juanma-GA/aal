import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Role(Base):
    """A per-material role (D5): analista, revisor, observador. Seeded by
    migration 0002; read-only in the UI for now."""

    __tablename__ = "role"

    code: Mapped[str] = mapped_column(String(50), primary_key=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)


class Permission(Base):
    """A permission with a stable code ("confunfis.editar"); the code is what
    the routes ask for (require_material_permission). `area` groups them for
    display (material, confunfis, ...)."""

    __tablename__ = "permission"

    code: Mapped[str] = mapped_column(String(100), primary_key=True)
    area: Mapped[str] = mapped_column(String(50), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)


class RolePermission(Base):
    """The matrix: which permissions each role has."""

    __tablename__ = "role_permission"

    role_code: Mapped[str] = mapped_column(String(50), ForeignKey("role.code", ondelete="CASCADE"), primary_key=True)
    permission_code: Mapped[str] = mapped_column(
        String(100), ForeignKey("permission.code", ondelete="CASCADE"), primary_key=True
    )


class UserMaterialRole(Base):
    """One role of one user on one material (one per pair)."""

    __tablename__ = "user_material_role"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True
    )
    material_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("material.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    role_code: Mapped[str] = mapped_column(String(50), ForeignKey("role.code"), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    assigned_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("app_user.id"), nullable=True)
