"""The CONFUNFIS of a CUF (E13, RF-02, NT 10/17 §9, Anexo XI sheet
CON_FUN_FIS): each physical component in its functional position.

A row: its position (SNS, CO component 01-99, AL alternative 00-99, QTY per
unit of its higher assembly), the article it is (article_id, and
article_reference_id when it goes by P/N + NCAGE; NULL when by NOC alone),
the name and function as the row gives them, CT SIGLE, and its higher
assembly (CS: the SNS + CO + AL of another row, or the CUF itself when
empty), kept as text exactly as given -- it may be badly formed.

No unique constraint on SNS + CO + AL + CS: a CONFUNFIS may hold errors for
the NT validator (E16) to find; the duplicates are marked, not prevented.
The graph (children, totals, orphans, cycles) is computed, never stored
(app/services/confunfis_graph.py); the light observations of each row are
(app/services/confunfis.py), until E16 replaces them by the CF rules.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# manual (the screen), seed (scripts/seed_demo_confunfis.py), import (E15),
# copia ("Crear a partir de otro").
POSITION_SOURCES = ("manual", "seed", "import", "copia")


class PhysicalPosition(Base):
    __tablename__ = "physical_position"
    __table_args__ = (
        CheckConstraint("source IN ('manual', 'seed', 'import', 'copia')", name="ck_physical_position_source"),
        Index("ix_physical_position_material_sns", "material_id", "sns"),
        Index("ix_physical_position_article", "article_id"),
        Index("ix_physical_position_observation_codes", "observation_codes", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    material_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("material.id", ondelete="CASCADE"), nullable=False)
    # Text as given (a file may bring them badly formed); the screen checks them.
    sns: Mapped[str] = mapped_column(String, nullable=False)
    co: Mapped[str] = mapped_column(String, nullable=False)
    al: Mapped[str] = mapped_column(String, nullable=False)
    qty: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    article_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("article.id", ondelete="SET NULL"), nullable=True)
    article_reference_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("article_reference.id", ondelete="SET NULL"), nullable=True
    )
    article_name: Mapped[str | None] = mapped_column(String, nullable=True)
    function_text: Mapped[str | None] = mapped_column(String, nullable=True)
    ct_sigle: Mapped[str | None] = mapped_column(String(1), nullable=True)
    cs_sns: Mapped[str | None] = mapped_column(String, nullable=True)
    cs_co: Mapped[str | None] = mapped_column(String, nullable=True)
    cs_al: Mapped[str | None] = mapped_column(String, nullable=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, server_default="manual")
    # What linking the article found that the row cannot hold (a P/N + NCAGE
    # of another article), and the row's light observations (codes OF-*).
    link_notes: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    observations: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    observation_codes: Mapped[list[str]] = mapped_column(ARRAY(String(10)), nullable=False, server_default=text("'{}'"))
    # The insert's own time (migration 0014): the order of rows with the same key (E15).
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.clock_timestamp())
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
