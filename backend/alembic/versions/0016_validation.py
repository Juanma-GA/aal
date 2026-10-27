"""E16: the NT 10/17 validator (app/models/validation.py): validation_rule,
seeded from the rules' catalog (app/validacion/catalog.py), validation_run,
validation_finding and finding_acceptance. No permission is added:
validating asks confunfis.ver and accepting a warning confunfis.editar,
both already in the matrix; the rules are the admin's.

The findings kept on the CONFUNFIS rows, parts, products and
incompatibilities change code (OF-*, OP-*, OPF-*, OI-* -> CF-*, TP-001,
PF-001): `backend/scripts/refresh_findings.py` (npm run update runs it
after a new migration) recomputes them.

Revision ID: 0016
Revises: 0015
"""

import json

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None

_SEVERITY = "severity IN ('bloqueante', 'aviso', 'desactivada')"


def _uuid(name: str, target: str | None = None, ondelete: str = "CASCADE", nullable: bool = False) -> sa.Column:
    if target is None:
        return sa.Column(name, postgresql.UUID(as_uuid=True), primary_key=True)
    return sa.Column(name, postgresql.UUID(as_uuid=True), sa.ForeignKey(target, ondelete=ondelete), nullable=nullable)


def upgrade() -> None:
    from app.validacion.catalog import CATALOG

    rules = op.create_table(
        "validation_rule",
        sa.Column("code", sa.String(10), primary_key=True),
        sa.Column("scope", sa.String(30), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("params", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("help", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        _uuid("updated_by", "app_user.id", "SET NULL", True),
        sa.CheckConstraint(_SEVERITY, name="ck_validation_rule_severity"),
    )
    op.bulk_insert(rules, [{"code": r.code, "scope": r.scope, "severity": r.severity, "params": json.loads(json.dumps(r.params))} for r in CATALOG])
    op.create_table(
        "validation_run",
        _uuid("id"),
        _uuid("material_id", "material.id"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        _uuid("user_id", "app_user.id", "SET NULL", True),
        sa.Column("trigger", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("rules_hash", sa.String(64), nullable=False),
        sa.Column("data_fingerprint", sa.String(64), nullable=False),
        sa.Column("blocking", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("warnings", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("accepted", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("seconds", sa.Float(), nullable=False, server_default=sa.text("0")),
    )
    op.create_index("ix_validation_run_material", "validation_run", ["material_id", "created_at"])
    op.create_table(
        "finding_acceptance",
        _uuid("id"),
        _uuid("material_id", "material.id"),
        sa.Column("rule_code", sa.String(10), nullable=False),
        sa.Column("entity_type", sa.String(30), nullable=False),
        sa.Column("entity_id", sa.String(64), nullable=False),
        sa.Column("problem", sa.String(60), nullable=False),
        sa.Column("justification", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        _uuid("created_by", "app_user.id", "SET NULL", True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_finding_acceptance_key", "finding_acceptance", ["material_id", "rule_code", "entity_type", "entity_id", "problem"])
    op.create_table(
        "validation_finding",
        _uuid("id"),
        _uuid("run_id", "validation_run.id"),
        sa.Column("rule_code", sa.String(10), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("scope", sa.String(30), nullable=False),
        sa.Column("entity_type", sa.String(30), nullable=False),
        sa.Column("entity_id", sa.String(64), nullable=False),
        sa.Column("problem", sa.String(60), nullable=False),
        sa.Column("params", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("field", sa.String(40), nullable=True),
        sa.Column("row_id", sa.String(64), nullable=True),
        sa.Column("location", sa.Text(), nullable=False),
        sa.Column("found", sa.Text(), nullable=True),
        sa.Column("expected", sa.Text(), nullable=True),
        _uuid("acceptance_id", "finding_acceptance.id", "SET NULL", True),
        sa.CheckConstraint("severity IN ('bloqueante', 'aviso')", name="ck_validation_finding_severity"),
    )
    op.create_index("ix_validation_finding_run", "validation_finding", ["run_id"])


def downgrade() -> None:
    op.drop_table("validation_finding")
    op.drop_table("finding_acceptance")
    op.drop_table("validation_run")
    op.drop_table("validation_rule")
