"""CONFUNFIS (E13, RF-02): physical_position, the rows of each CUF's
functional physical configuration (app/models/confunfis.py); the article's
origin (a provisional one born from a CONFUNFIS row); and the module
"Configuración funcional física" turned on at /materiales/:materialId/confunfis.

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-26

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MODULE = "confunfis"
ROUTE = "/materiales/:materialId/confunfis"


def upgrade() -> None:
    op.add_column("article", sa.Column("origin", sa.String(20), nullable=False, server_default="maestro"))
    op.create_check_constraint("ck_article_origin", "article", "origin IN ('maestro', 'confunfis')")
    op.create_table(
        "physical_position",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("material_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("material.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sns", sa.String(), nullable=False),
        sa.Column("co", sa.String(), nullable=False),
        sa.Column("al", sa.String(), nullable=False),
        sa.Column("qty", sa.Numeric(), nullable=True),
        sa.Column("article_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("article.id", ondelete="SET NULL"), nullable=True),
        sa.Column("article_reference_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("article_reference.id", ondelete="SET NULL"), nullable=True),
        sa.Column("article_name", sa.String(), nullable=True),
        sa.Column("function_text", sa.String(), nullable=True),
        sa.Column("ct_sigle", sa.String(1), nullable=True),
        sa.Column("cs_sns", sa.String(), nullable=True),
        sa.Column("cs_co", sa.String(), nullable=True),
        sa.Column("cs_al", sa.String(), nullable=True),
        sa.Column("source", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("link_notes", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("observations", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("observation_codes", postgresql.ARRAY(sa.String(10)), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.CheckConstraint("source IN ('manual', 'seed', 'import', 'copia')", name="ck_physical_position_source"),
    )
    op.create_index("ix_physical_position_material_sns", "physical_position", ["material_id", "sns"])
    op.create_index("ix_physical_position_article", "physical_position", ["article_id"])
    op.create_index("ix_physical_position_observation_codes", "physical_position", ["observation_codes"], postgresql_using="gin")
    op.execute(
        sa.text("UPDATE module_catalog SET status = 'disponible', route = :route, version = version + 1 WHERE code = :code").bindparams(
            route=ROUTE, code=MODULE
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text("UPDATE module_catalog SET status = 'planificado', route = NULL, version = version + 1 WHERE code = :code").bindparams(code=MODULE)
    )
    op.drop_table("physical_position")
    op.drop_constraint("ck_article_origin", "article", type_="check")
    op.drop_column("article", "origin")
