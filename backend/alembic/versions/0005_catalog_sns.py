"""Normalized functional configuration (E10, NT 10/17 Anexo II):
catalog_version, material_category, material_subcategory, sns_position,
subcategory_sns, sns_extra_name.

The catalog itself arrives by importing a CONF_FUN file (an admin, through
the app): nothing is loaded here. The module "Configuración funcional
normalizada" is turned on (status disponible and its route), as the seed
says: a reload of the module catalog never changes an existing status.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-22

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MODULE = "catalogo-normalizado"
ROUTE = "/configuracion-funcional"


def _version_fk() -> sa.Column:
    return sa.Column("version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("catalog_version.id", ondelete="CASCADE"), nullable=False)


def upgrade() -> None:
    op.create_table(
        "catalog_version",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("number", sa.Integer(), nullable=False, unique=True),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_sha256", sa.String(64), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("counts", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("warnings", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.create_index("uq_catalog_version_active", "catalog_version", ["is_active"], unique=True, postgresql_where=sa.text("is_active"))
    op.create_table(
        "material_category",
        sa.Column("code", sa.String(2), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
    )
    op.create_table(
        "material_subcategory",
        sa.Column("code", sa.String(4), primary_key=True),
        sa.Column("category_code", sa.String(2), sa.ForeignKey("material_category.code"), nullable=False),
        sa.Column("sub_code", sa.String(2), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.UniqueConstraint("category_code", "sub_code", name="uq_material_subcategory"),
    )
    op.create_table(
        "sns_position",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        _version_fk(),
        sa.Column("sns", sa.String(6), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("description_pending", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("level", sa.String(20), nullable=False),
        sa.Column("parent_sns", sa.String(6), nullable=True),
        sa.Column("declared_levels", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.UniqueConstraint("version_id", "sns", name="uq_sns_position"),
    )
    op.create_index("ix_sns_position_parent", "sns_position", ["version_id", "parent_sns"])
    op.create_table(
        "subcategory_sns",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        _version_fk(),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("subcategory_code", sa.String(4), sa.ForeignKey("material_subcategory.code"), nullable=True),
        sa.Column("category_code", sa.String(2), nullable=True),
        sa.Column("category_name", sa.String(200), nullable=True),
        sa.Column("sub_code", sa.String(2), nullable=True),
        sa.Column("subcategory_name", sa.String(200), nullable=True),
        sa.Column("sns", sa.String(6), nullable=False),
        sa.Column("declared_level", sa.String(20), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("description_repaired", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_index("ix_subcategory_sns_version_sub", "subcategory_sns", ["version_id", "subcategory_code", "sns"])
    op.create_index("ix_subcategory_sns_version_sns", "subcategory_sns", ["version_id", "sns"])
    op.create_table(
        "sns_extra_name",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        _version_fk(),
        sa.Column("sns", sa.String(6), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("origin", sa.String(20), nullable=False),
        sa.UniqueConstraint("version_id", "sns", "name", name="uq_sns_extra_name"),
    )
    op.execute(
        sa.text("UPDATE module_catalog SET status = 'disponible', route = :route, version = version + 1 WHERE code = :code").bindparams(
            route=ROUTE, code=MODULE
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text("UPDATE module_catalog SET status = 'planificado', route = NULL, version = version + 1 WHERE code = :code").bindparams(code=MODULE)
    )
    op.drop_table("sns_extra_name")
    op.drop_index("ix_subcategory_sns_version_sns", table_name="subcategory_sns")
    op.drop_index("ix_subcategory_sns_version_sub", table_name="subcategory_sns")
    op.drop_table("subcategory_sns")
    op.drop_index("ix_sns_position_parent", table_name="sns_position")
    op.drop_table("sns_position")
    op.drop_table("material_subcategory")
    op.drop_table("material_category")
    op.drop_index("uq_catalog_version_active", table_name="catalog_version")
    op.drop_table("catalog_version")
