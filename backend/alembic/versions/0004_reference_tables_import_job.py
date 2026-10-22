"""Reference tables and Excel imports (E03): reference_table,
reference_value, article_field_definition, import_job.

The reference tables and the 30 article fields are filled from
app/seeds/reference_tables_seed.yaml by app/services/reference_seed.py (the
same idempotent loader as scripts/load_reference_tables.py): 15 tables
(7 SIGLE, 8 NT 10/17) with their values, codes always text. The seed is
checked first; a seed that fails stops the migration.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-22

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    ]


def upgrade() -> None:
    op.create_table(
        "reference_table",
        sa.Column("code", sa.String(40), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("source", sa.Text(), nullable=False, server_default=""),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("editable", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("attribute_schema", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        *_timestamps(),
    )
    op.create_table(
        "reference_value",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("table_code", sa.String(40), sa.ForeignKey("reference_table.code"), nullable=False),
        sa.Column("code", sa.String(30), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("definition", sa.Text(), nullable=True),
        sa.Column("attributes", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        *_timestamps(),
        sa.UniqueConstraint("table_code", "code", name="uq_reference_value_table_code"),
        sa.CheckConstraint("code <> '' AND code = btrim(code)", name="ck_reference_value_code"),
    )
    op.create_index("ix_reference_value_table_code", "reference_value", ["table_code"])
    op.create_table(
        "article_field_definition",
        sa.Column("prisma_code", sa.String(40), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("importance", sa.String(40), nullable=False),
        sa.Column("guide_field", sa.String(20), nullable=False),
        sa.Column("data_type", sa.String(40), nullable=False),
        sa.Column("length", sa.Integer(), nullable=True),
        sa.Column("decimals", sa.Integer(), nullable=True),
        sa.Column("related_to", sa.String(100), nullable=True),
        sa.Column("supplied_by_contractor", sa.String(200), nullable=False),
        sa.Column("reference_table_code", sa.String(40), sa.ForeignKey("reference_table.code"), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
    )
    op.create_table(
        "import_job",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("template", sa.String(50), nullable=False),
        sa.Column("params", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("app_user.id"), nullable=False),
        sa.Column("material_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("material.id"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_sha256", sa.String(64), nullable=False),
        sa.Column("counts", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("report", postgresql.JSONB(), nullable=True),
        sa.Column("error_code", sa.String(60), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("status IN ('analyzing', 'analyzed', 'applied', 'failed')", name="ck_import_job_status"),
    )
    op.create_index("ix_import_job_user_id", "import_job", ["user_id"])

    from app.services.reference_seed import load_reference_tables

    load_reference_tables(op.get_bind())


def downgrade() -> None:
    op.drop_index("ix_import_job_user_id", table_name="import_job")
    op.drop_table("import_job")
    op.drop_table("article_field_definition")
    op.drop_index("ix_reference_value_table_code", table_name="reference_value")
    op.drop_table("reference_value")
    op.drop_table("reference_table")
