"""Baselines and change authorizations of a CUF (E17, S3000L ch. 4):

- Baseline: an immutable snapshot of a CUF's CONFUNFIS (`scope`
  "confunfis"; "cil" for E19), numbered v1, v2…, reviewed by someone other
  than its author. `snapshot` is one JSON document (app/services/baselines.py):
  the rows, products, extra functions and incompatibilities, a copy of the
  articles they use (their SIGLE data, references and parts: those are
  global and change afterwards) and the very sheets the delivery exports.
  `snapshot_hash` is its SHA-256: nothing ever writes it again.
- ChangeAuthorization: AC-<CUF>-NNN, needed to change a CONFUNFIS once it
  has a reviewed baseline; requested, approved or rejected by someone else,
  closed by hand or when the next baseline is reviewed.
- AuthorizationChange: each record a change made under an authorization
  touched (entity, id, action), for the diff and the row's history.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

SCOPES = ("confunfis", "cil")
STATES = ("en_revision", "revisada", "rechazada", "retirada")
AUTHORIZATION_STATES = ("solicitada", "aprobada", "rechazada", "cerrada")
ACTIONS = ("creado", "modificado", "eliminado")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class Baseline(Base):
    __tablename__ = "baseline"
    __table_args__ = (
        CheckConstraint(_in("scope", SCOPES), name="ck_baseline_scope"),
        CheckConstraint(_in("state", STATES), name="ck_baseline_state"),
        Index("uq_baseline_number", "material_id", "scope", "number", unique=True),
        # One baseline in review per CUF and scope at a time.
        Index("uq_baseline_in_review", "material_id", "scope", unique=True, postgresql_where=text("state = 'en_revision'")),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    material_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("material.id", ondelete="CASCADE"), nullable=False)
    scope: Mapped[str] = mapped_column(String(20), nullable=False, server_default="confunfis")
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False, server_default="en_revision")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.clock_timestamp())
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True)
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The validation it was frozen with: kept for good (validation.RETAINED_RUNS).
    validation_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("validation_run.id", ondelete="RESTRICT"), nullable=True)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    data_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class ChangeAuthorization(Base):
    __tablename__ = "change_authorization"
    __table_args__ = (
        CheckConstraint(_in("state", AUTHORIZATION_STATES), name="ck_change_authorization_state"),
        Index("uq_change_authorization_number", "material_id", "number", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    material_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("material.id", ondelete="CASCADE"), nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    # AC-<CUF>-NNN, as written when it was requested.
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    # A code of the reference table TIPO_AUTORIZACION (configurable).
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False, server_default="solicitada")
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.clock_timestamp())
    requested_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True)
    decision_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True)
    # The baseline whose review closed it (None: closed by hand).
    closed_in_baseline_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("baseline.id", ondelete="SET NULL"), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class AuthorizationChange(Base):
    __tablename__ = "authorization_change"
    __table_args__ = (
        CheckConstraint(_in("action", ACTIONS), name="ck_authorization_change_action"),
        Index("ix_authorization_change_material", "material_id", "created_at"),
        Index("ix_authorization_change_entity", "entity_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    authorization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("change_authorization.id", ondelete="CASCADE"), nullable=False)
    material_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("material.id", ondelete="CASCADE"), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.clock_timestamp())
