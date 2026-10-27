"""E17: baselines and change authorizations of a CUF (app/models/baseline.py):
baseline, change_authorization and authorization_change; and the reference
table TIPO_AUTORIZACION (the kinds of authorization), from the seed.

Revision ID: 0019
Revises: 0018
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def _user(name: str) -> sa.Column:
    return sa.Column(name, postgresql.UUID(as_uuid=True), sa.ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True)


def _material() -> sa.Column:
    return sa.Column("material_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("material.id", ondelete="CASCADE"), nullable=False)


def upgrade() -> None:
    op.create_table(
        "baseline",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _material(),
        sa.Column("scope", sa.String(20), nullable=False, server_default="confunfis"),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(20), nullable=False, server_default="en_revision"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        _user("created_by"),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        _user("reviewed_by"),
        sa.Column("review_comment", sa.Text(), nullable=True),
        sa.Column("validation_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("validation_run.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("snapshot_hash", sa.String(64), nullable=False),
        sa.Column("data_fingerprint", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.CheckConstraint("scope IN ('confunfis', 'cil')", name="ck_baseline_scope"),
        sa.CheckConstraint("state IN ('en_revision', 'revisada', 'rechazada', 'retirada')", name="ck_baseline_state"),
    )
    op.create_index("uq_baseline_number", "baseline", ["material_id", "scope", "number"], unique=True)
    op.create_index("uq_baseline_in_review", "baseline", ["material_id", "scope"], unique=True, postgresql_where=sa.text("state = 'en_revision'"))
    op.create_table(
        "change_authorization",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _material(),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("state", sa.String(20), nullable=False, server_default="solicitada"),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        _user("requested_by"),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        _user("decided_by"),
        sa.Column("decision_comment", sa.Text(), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        _user("closed_by"),
        sa.Column("closed_in_baseline_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("baseline.id", ondelete="SET NULL"), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.CheckConstraint("state IN ('solicitada', 'aprobada', 'rechazada', 'cerrada')", name="ck_change_authorization_state"),
    )
    op.create_index("uq_change_authorization_number", "change_authorization", ["material_id", "number"], unique=True)
    op.create_table(
        "authorization_change",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("authorization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("change_authorization.id", ondelete="CASCADE"), nullable=False),
        _material(),
        sa.Column("entity_type", sa.String(40), nullable=False),
        sa.Column("entity_id", sa.String(64), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        _user("user_id"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.CheckConstraint("action IN ('creado', 'modificado', 'eliminado')", name="ck_authorization_change_action"),
    )
    op.create_index("ix_authorization_change_material", "authorization_change", ["material_id", "created_at"])
    op.create_index("ix_authorization_change_entity", "authorization_change", ["entity_id"])

    from app.services.reference_seed import load_reference_tables

    load_reference_tables(op.get_bind())


def downgrade() -> None:
    op.drop_table("authorization_change")
    op.drop_table("change_authorization")
    op.drop_table("baseline")
    op.execute("DELETE FROM reference_value WHERE table_code = 'TIPO_AUTORIZACION'")
    op.execute("DELETE FROM reference_table WHERE code = 'TIPO_AUTORIZACION'")
