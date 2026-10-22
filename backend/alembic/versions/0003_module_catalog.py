"""PALI module catalog (E02): module_group, module_catalog, module_requirement.

The tables are created here and filled from
app/seeds/module_catalog_seed.yaml by app/services/module_catalog.py (the
same idempotent loader as scripts/load_module_catalog.py): 9 groups, 45
modules, their requirements RF-01..RF-41. The seed is checked first
(unique codes, known groups, known dependencies without cycles, every RF
covered); a seed that fails stops the migration.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-22

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "module_group",
        sa.Column("code", sa.String(50), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
    )
    op.create_table(
        "module_catalog",
        sa.Column("code", sa.String(50), primary_key=True),
        sa.Column("group_code", sa.String(50), sa.ForeignKey("module_group.code"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("phase", sa.String(10), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="planificado"),
        sa.Column("encargo", sa.String(50), nullable=True),
        sa.Column("objective", sa.Text(), nullable=False, server_default=""),
        sa.Column("inputs", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("outputs", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("deliverable", sa.Text(), nullable=True),
        sa.Column("dependencies", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("route", sa.String(200), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("status IN ('planificado', 'en_desarrollo', 'disponible')", name="ck_module_catalog_status"),
        sa.CheckConstraint("(status = 'disponible') = (route IS NOT NULL)", name="ck_module_catalog_route"),
    )
    op.create_index("ix_module_catalog_group_code", "module_catalog", ["group_code"])
    op.create_table(
        "module_requirement",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("module_code", sa.String(50), sa.ForeignKey("module_catalog.code", ondelete="CASCADE"), nullable=False),
        sa.Column("rf_id", sa.String(10), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
    )
    op.create_index("ix_module_requirement_module_code", "module_requirement", ["module_code"])

    from app.services.module_catalog import load_catalog

    load_catalog(op.get_bind())


def downgrade() -> None:
    op.drop_table("module_requirement")
    op.drop_index("ix_module_catalog_group_code", table_name="module_catalog")
    op.drop_table("module_catalog")
    op.drop_table("module_group")
