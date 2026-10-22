"""Users, sessions, minimal material and roles per material (E01).

- app_user: who signs in ("user" is reserved in PostgreSQL). Email unique
  (stored lower case), is_admin, is_active, soft delete (deleted_at /
  deleted_by, HR9), ui_preferences (JSONB, HR1), must_change_password and
  version (optimistic locking, D10).
- refresh_token: SHA-256 of each refresh token, its family (one per login)
  and why it was revoked (rotation, logout, reuse detected...).
- login_failure: failed logins, counted per email and per address.
- material: the minimal CUF (D12): NOC (13, optional, unique among the
  materials not deleted), name, P/N, NCAGE (5), description, soft delete
  and version. E11 completes it.
- role, permission, role_permission: the catalogue and the seed matrix
  (D5), with the permissions E10-E19 will need already in, so the matrix
  is not migrated again in each encargo. user_material_role: one role per
  user and material.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-22

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLES = ("analista", "revisor", "observador")

# (code, area). The order is the display order.
PERMISSIONS = (
    ("material.ver", "material"),
    ("material.editar", "material"),
    ("catalogo.ver", "catalogo"),
    ("confunfis.ver", "confunfis"),
    ("confunfis.editar", "confunfis"),
    ("articulos.ver", "articulos"),
    ("articulos.editar", "articulos"),
    ("candidatos.ver", "candidatos"),
    ("candidatos.editar", "candidatos"),
    ("tareas.ver", "tareas"),
    ("tareas.editar", "tareas"),
    ("validacion.ver", "validacion"),
    ("validacion.ejecutar", "validacion"),
    ("revision.enviar", "revision"),
    ("revision.aprobar", "revision"),
    ("exportar", "exportacion"),
)

_ALL = set(ROLES)
_VIEW = {code: _ALL for code, _ in PERMISSIONS if code.endswith(".ver")}
# The seed matrix of encargo E01, §2.2.
MATRIX = {
    **_VIEW,
    "material.editar": {"analista"},
    "confunfis.editar": {"analista"},
    "articulos.editar": {"analista"},
    "candidatos.editar": {"analista"},
    "tareas.editar": {"analista"},
    "revision.enviar": {"analista"},
    "revision.aprobar": {"revisor"},
    "validacion.ejecutar": {"analista", "revisor"},
    "exportar": _ALL,
}


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    ]


def upgrade() -> None:
    op.create_table(
        "app_user",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("password_hash", sa.String(100), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("ui_preferences", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        *_timestamps(),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("app_user.id"), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.CheckConstraint("email = lower(email)", name="ck_app_user_email_lower"),
    )

    op.create_table(
        "refresh_token",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason", sa.String(30), nullable=True),
    )
    op.create_index("ix_refresh_token_user_id", "refresh_token", ["user_id"])
    op.create_index("ix_refresh_token_family_id", "refresh_token", ["family_id"])

    op.create_table(
        "login_failure",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("ip", postgresql.INET(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_login_failure_email_created_at", "login_failure", ["email", "created_at"])
    op.create_index("ix_login_failure_ip_created_at", "login_failure", ["ip", "created_at"])

    op.create_table(
        "material",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("noc", sa.String(13), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("part_number", sa.String(32), nullable=True),
        sa.Column("ncage", sa.String(5), nullable=True),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        *_timestamps(),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("app_user.id"), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.CheckConstraint("noc IS NULL OR length(noc) = 13", name="ck_material_noc_length"),
        sa.CheckConstraint("ncage IS NULL OR length(ncage) = 5", name="ck_material_ncage_length"),
    )
    op.create_index(
        "uq_material_noc_active",
        "material",
        ["noc"],
        unique=True,
        postgresql_where=sa.text("noc IS NOT NULL AND deleted_at IS NULL"),
    )

    role = op.create_table(
        "role",
        sa.Column("code", sa.String(50), primary_key=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
    )
    permission = op.create_table(
        "permission",
        sa.Column("code", sa.String(100), primary_key=True),
        sa.Column("area", sa.String(50), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
    )
    role_permission = op.create_table(
        "role_permission",
        sa.Column("role_code", sa.String(50), sa.ForeignKey("role.code", ondelete="CASCADE"), primary_key=True),
        sa.Column("permission_code", sa.String(100), sa.ForeignKey("permission.code", ondelete="CASCADE"), primary_key=True),
    )
    op.create_table(
        "user_material_role",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("material_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("material.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role_code", sa.String(50), sa.ForeignKey("role.code"), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("assigned_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("app_user.id"), nullable=True),
    )
    op.create_index("ix_user_material_role_material_id", "user_material_role", ["material_id"])

    op.bulk_insert(role, [{"code": code, "sort_order": i} for i, code in enumerate(ROLES, start=1)])
    op.bulk_insert(
        permission, [{"code": code, "area": area, "sort_order": i} for i, (code, area) in enumerate(PERMISSIONS, start=1)]
    )
    op.bulk_insert(
        role_permission,
        [
            {"role_code": role_code, "permission_code": code}
            for code, _ in PERMISSIONS
            for role_code in ROLES
            if role_code in MATRIX.get(code, set())
        ],
    )


def downgrade() -> None:
    op.drop_table("user_material_role")
    op.drop_table("role_permission")
    op.drop_table("permission")
    op.drop_table("role")
    op.drop_index("uq_material_noc_active", table_name="material")
    op.drop_table("material")
    op.drop_table("login_failure")
    op.drop_table("refresh_token")
    op.drop_table("app_user")
