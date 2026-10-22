import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# Longest code a reference value may have (the seed's longest is 13).
REFERENCE_CODE_MAX_LENGTH = 30
# Longest description and definition (the seed's longest: 390 and 256).
REFERENCE_DESCRIPTION_MAX_LENGTH = 1000
REFERENCE_DEFINITION_MAX_LENGTH = 2000
# Types of a value's attribute (reference_table.attribute_schema).
ATTRIBUTE_TYPES = ("texto", "entero", "si_no")


class ReferenceTable(Base):
    """A reference table (E03, RNF-07): SIGLE (D106, D107, D112...) or NT
    10/17 (M101, CRITICIDAD...). Name, source, note and the attribute
    schema come from app/seeds/reference_tables_seed.yaml; the values are
    edited by an admin.

    attribute_schema: [{"key", "name", "type" (ATTRIBUTE_TYPES), "required",
    "options": [{"code", "name"}]}] -- what a value's `attributes` may hold,
    with the readable names shown instead of the keys (HR21)."""

    __tablename__ = "reference_table"

    code: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    editable: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    attribute_schema: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ReferenceValue(Base):
    """One value of a reference table. The code is always text ("0", "02"
    keep their zeros). Never deleted (HR9): a deactivated value still
    resolves for the data that already uses it, but new data cannot pick
    it."""

    __tablename__ = "reference_value"
    __table_args__ = (
        UniqueConstraint("table_code", "code", name="uq_reference_value_table_code"),
        CheckConstraint("code <> '' AND code = btrim(code)", name="ck_reference_value_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    table_code: Mapped[str] = mapped_column(String(40), ForeignKey("reference_table.code"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(REFERENCE_CODE_MAX_LENGTH), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    definition: Mapped[str | None] = mapped_column(Text, nullable=True)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ArticleFieldDefinition(Base):
    """One of the 30 fields of an article (Fichero Carga / MAR06): metadata
    E12 validates articles with. Read-only: it comes from the seed."""

    __tablename__ = "article_field_definition"

    prisma_code: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    importance: Mapped[str] = mapped_column(String(40), nullable=False)
    guide_field: Mapped[str] = mapped_column(String(20), nullable=False)
    data_type: Mapped[str] = mapped_column(String(40), nullable=False)
    length: Mapped[int | None] = mapped_column(Integer, nullable=True)
    decimals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    related_to: Mapped[str | None] = mapped_column(String(100), nullable=True)
    supplied_by_contractor: Mapped[str] = mapped_column(String(200), nullable=False)
    reference_table_code: Mapped[str | None] = mapped_column(String(40), ForeignKey("reference_table.code"), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
