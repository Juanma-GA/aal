"""The NT 10/17 validator (E16, RF-03):

- ValidationRule: a rule's configuration, seeded from the catalog
  (app/validacion/catalog.py): active, severity, parameters and help text,
  changed by the admin (audited, with a version).
- ValidationRun: one validation of a CUF -- who, when, the rules'
  configuration it used (`rules_hash`), what it saw (`data_fingerprint`:
  a later change makes it "desactualizado") and its counts.
- ValidationFinding: a finding of a run, with the severity it had then and
  a readable location ("A24110 01 00 · FILTRO DE AIRE").
- FindingAcceptance: a warning accepted with its justification, for a CUF;
  it holds for every later run where the same finding comes back.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

SEVERITY_CHECK = "severity IN ('bloqueante', 'aviso', 'desactivada')"


class ValidationRule(Base):
    __tablename__ = "validation_rule"
    __table_args__ = (CheckConstraint(SEVERITY_CHECK, name="ck_validation_rule_severity"),)

    code: Mapped[str] = mapped_column(String(10), primary_key=True)
    scope: Mapped[str] = mapped_column(String(30), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    # The admin's own help text (the default lives in es.json).
    help: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True)


class ValidationRun(Base):
    __tablename__ = "validation_run"
    __table_args__ = (Index("ix_validation_run_material", "material_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    material_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("material.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.clock_timestamp())
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True)
    # "manual", "import" (after applying a book).
    trigger: Mapped[str] = mapped_column(String(20), nullable=False, server_default="manual")
    rules_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    data_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    blocking: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    warnings: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    accepted: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    seconds: Mapped[float] = mapped_column(nullable=False, server_default=text("0"))


class ValidationFinding(Base):
    __tablename__ = "validation_finding"
    __table_args__ = (Index("ix_validation_finding_run", "run_id"), CheckConstraint("severity IN ('bloqueante', 'aviso')", name="ck_validation_finding_severity"))

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("validation_run.id", ondelete="CASCADE"), nullable=False)
    rule_code: Mapped[str] = mapped_column(String(10), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    scope: Mapped[str] = mapped_column(String(30), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    problem: Mapped[str] = mapped_column(String(60), nullable=False)
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    field: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # The CONFUNFIS row "Ir a" opens (an article, a part: the first row with it).
    row_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    location: Mapped[str] = mapped_column(Text, nullable=False)
    found: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected: Mapped[str | None] = mapped_column(Text, nullable=True)
    acceptance_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("finding_acceptance.id", ondelete="SET NULL"), nullable=True)


class FindingAcceptance(Base):
    __tablename__ = "finding_acceptance"
    __table_args__ = (Index("ix_finding_acceptance_key", "material_id", "rule_code", "entity_type", "entity_id", "problem"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    material_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("material.id", ondelete="CASCADE"), nullable=False)
    rule_code: Mapped[str] = mapped_column(String(10), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    problem: Mapped[str] = mapped_column(String(60), nullable=False)
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True)
    # Withdrawn (soft, HR9): the finding counts again.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
