import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# analyzing -> analyzed -> applied; any of the first two can end in failed
# (a broken file, an interrupted analysis, a stale one reaped).
IMPORT_JOB_STATUSES = ("analyzing", "analyzed", "applied", "failed")


class ImportJob(Base):
    """An Excel import (E03, app/io_excel): the file is analysed in the
    background into `report` (new, modified, unchanged, errors, warnings)
    without touching the target tables; applying it is a separate step on
    this very analysis. Postgres is the only record of where it stands
    (HR1)."""

    __tablename__ = "import_job"
    __table_args__ = (
        CheckConstraint("status IN ('analyzing', 'analyzed', 'applied', 'failed')", name="ck_import_job_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # The import target (app/io_excel/targets.py) and its parameters, e.g.
    # "reference_table" with {"table": "D112"}.
    template: Mapped[str] = mapped_column(String(50), nullable=False)
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("app_user.id"), nullable=False, index=True)
    material_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("material.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    counts: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    report: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    # Why it failed (an error code the frontend translates), or None.
    error_code: Mapped[str | None] = mapped_column(String(60), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
