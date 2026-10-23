"""Materials / CUF (E11): the CUF's catalog version, Grupo-Clase and the
CUF it was copied from, its subcategories (material_subcategory_link) and
the requests for a new SNS (sns_request).

Materials that exist get the active catalog version, if there is one. The
module "Materiales / CUF" is turned on (status disponible and its route).

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-23

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MODULE = "materiales"
ROUTE = "/materiales/:materialId/ficha"


def upgrade() -> None:
    op.add_column(
        "material",
        sa.Column("catalog_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("catalog_version.id", ondelete="SET NULL"), nullable=True),
    )
    op.add_column("material", sa.Column("grupo_clase", sa.String(4), nullable=True))
    op.add_column(
        "material",
        sa.Column("copied_from_material_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("material.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_check_constraint("ck_material_grupo_clase", "material", "grupo_clase IS NULL OR grupo_clase ~ '^[0-9]{4}$'")
    op.create_table(
        "material_subcategory_link",
        sa.Column("material_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("material.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("subcategory_code", sa.String(4), sa.ForeignKey("material_subcategory.code"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_table(
        "sns_request",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("material_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("material.id"), nullable=False),
        sa.Column("proposed_sns", sa.String(6), nullable=True),
        sa.Column("parent_sns", sa.String(6), nullable=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("function", sa.Text(), nullable=False, server_default=""),
        sa.Column("justification", sa.Text(), nullable=False),
        sa.Column("state", sa.String(20), nullable=False, server_default="borrador"),
        sa.Column("response", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("resolved_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.CheckConstraint("state IN ('borrador', 'enviada', 'aceptada', 'rechazada')", name="ck_sns_request_state"),
    )
    op.create_index("ix_sns_request_material_id", "sns_request", ["material_id"])
    op.execute("UPDATE material SET catalog_version_id = (SELECT id FROM catalog_version WHERE is_active) WHERE catalog_version_id IS NULL")
    op.execute(
        sa.text("UPDATE module_catalog SET status = 'disponible', route = :route, version = version + 1 WHERE code = :code").bindparams(
            route=ROUTE, code=MODULE
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text("UPDATE module_catalog SET status = 'en_desarrollo', route = NULL, version = version + 1 WHERE code = :code").bindparams(code=MODULE)
    )
    op.drop_index("ix_sns_request_material_id", table_name="sns_request")
    op.drop_table("sns_request")
    op.drop_table("material_subcategory_link")
    op.drop_constraint("ck_material_grupo_clase", "material", type_="check")
    op.drop_column("material", "copied_from_material_id")
    op.drop_column("material", "grupo_clase")
    op.drop_column("material", "catalog_version_id")
