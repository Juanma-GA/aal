"""The rest of RF-02 (E14): article_part (the parts table of an article),
functional_product, extra_function (multifunction components) and
incompatibility (app/models/confunfis_extras.py); and the reference table
CRITERIO_MULTIFUNCION, loaded from the seed.

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-26

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _audited() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
    ]


def _observed() -> list[sa.Column]:
    return [
        sa.Column("observations", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("observation_codes", postgresql.ARRAY(sa.String(10)), nullable=False, server_default=sa.text("'{}'")),
    ]


def _uuid(name: str, target: str | None = None, ondelete: str = "CASCADE", nullable: bool = False) -> sa.Column:
    if target is None:
        return sa.Column(name, postgresql.UUID(as_uuid=True), primary_key=True)
    return sa.Column(name, postgresql.UUID(as_uuid=True), sa.ForeignKey(target, ondelete=ondelete), nullable=nullable)


def upgrade() -> None:
    op.create_table(
        "article_part",
        _uuid("id"),
        _uuid("parent_article_id", "article.id"),
        sa.Column("cop", sa.String(), nullable=False),
        sa.Column("alp", sa.String(), nullable=False),
        _uuid("part_article_id", "article.id", "SET NULL", True),
        _uuid("article_reference_id", "article_reference.id", "SET NULL", True),
        sa.Column("part_name", sa.String(), nullable=True),
        sa.Column("quantity", sa.Numeric(), nullable=True),
        sa.Column("source", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("link_notes", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        *_audited(),
        *_observed(),
        sa.CheckConstraint("source IN ('manual', 'seed', 'import')", name="ck_article_part_source"),
    )
    op.create_index("ix_article_part_parent", "article_part", ["parent_article_id"])
    op.create_index("ix_article_part_part", "article_part", ["part_article_id"])

    op.create_table(
        "functional_product",
        _uuid("id"),
        _uuid("material_id", "material.id"),
        sa.Column("designation", sa.String(), nullable=False),
        sa.Column("pol_code", sa.String(), nullable=True),
        sa.Column("nae", sa.String(), nullable=True),
        sa.Column("noc", sa.String(), nullable=True),
        _uuid("article_id", "article.id", "SET NULL", True),
        sa.Column("supply_unit", sa.String(), nullable=True),
        sa.Column("quantity", sa.Numeric(), nullable=True),
        sa.Column("unit", sa.String(), nullable=True),
        sa.Column("source", sa.String(20), nullable=False, server_default="manual"),
        *_audited(),
        *_observed(),
        sa.CheckConstraint("source IN ('manual', 'seed', 'import', 'copia')", name="ck_functional_product_source"),
    )
    op.create_index("ix_functional_product_material", "functional_product", ["material_id"])
    op.create_index("ix_functional_product_article", "functional_product", ["article_id"])

    op.create_table(
        "extra_function",
        _uuid("id"),
        _uuid("material_id", "material.id"),
        _uuid("position_id", "physical_position.id"),
        sa.Column("sns", sa.String(), nullable=False),
        sa.Column("criterion", sa.String(), nullable=False),
        sa.Column("comment", sa.String(), nullable=True),
        sa.Column("source", sa.String(20), nullable=False, server_default="manual"),
        *_audited(),
        sa.CheckConstraint("source IN ('manual', 'seed', 'import', 'copia')", name="ck_extra_function_source"),
    )
    op.create_index("ix_extra_function_position", "extra_function", ["position_id"])
    op.create_index("ix_extra_function_material", "extra_function", ["material_id"])

    op.create_table(
        "incompatibility",
        _uuid("id"),
        _uuid("material_id", "material.id"),
        _uuid("row_a_id", "physical_position.id"),
        _uuid("row_b_id", "physical_position.id"),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("source", sa.String(20), nullable=False, server_default="manual"),
        *_audited(),
        *_observed(),
        sa.CheckConstraint("kind IN ('excluye', 'requiere')", name="ck_incompatibility_kind"),
        sa.CheckConstraint("row_a_id <> row_b_id", name="ck_incompatibility_distinct"),
        sa.CheckConstraint("source IN ('manual', 'seed', 'import', 'copia')", name="ck_incompatibility_source"),
    )
    op.create_index("ix_incompatibility_material", "incompatibility", ["material_id"])
    op.create_index("ix_incompatibility_a", "incompatibility", ["row_a_id"])
    op.create_index("ix_incompatibility_b", "incompatibility", ["row_b_id"])

    # CRITERIO_MULTIFUNCION: a new table of the seed (a reload adds it).
    from app.services.reference_seed import load_reference_tables

    load_reference_tables(op.get_bind())


def downgrade() -> None:
    op.drop_table("incompatibility")
    op.drop_table("extra_function")
    op.drop_table("functional_product")
    op.drop_table("article_part")
    op.execute("DELETE FROM reference_value WHERE table_code = 'CRITERIO_MULTIFUNCION'")
    op.execute("DELETE FROM reference_table WHERE code = 'CRITERIO_MULTIFUNCION'")
