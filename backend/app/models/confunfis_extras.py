"""The rest of RF-02 (E14, NT 10/17 §9.1.1, §9.1.10, §9.1.11):

- ArticlePart: the parts table of an article (§9.1.10) -- the components of
  its breakdown that are not in any CONFUNFIS but count in the reliability
  and maintainability analyses. It belongs to the article, not to a CUF
  (D16): the water pump DM-6 breaks down the same in every CUF that mounts
  it. COP 01-99 is the part, ALP 00-99 its alternative; the quantity is per
  unit of the article.
- FunctionalProduct: an oil, fuel, grease... of the CUF (§9.1.11), by its
  POL code, N/A/E, NOC (linked with the master when the article exists; no
  provisional ones), supply unit (D155), quantity in it (none: in bulk) and
  unit of measure (D112).
- ExtraFunction: another function (SNS) of a CONFUNFIS row that sits in one
  position only (a multifunction component, §9.1.1), with the criterion of
  its placement and a comment.
- Incompatibility: a restriction between two rows of a CUF that CO/AL/CS do
  not express: "excluye" (symmetric, stored once) or "requiere" (A needs B).

Like physical_position, none has a unique constraint in the database: the
errors stay for E16 and are marked as observations (codes OP-*, OPF-*, OI-*,
provisional).
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

INCOMPATIBILITY_KINDS = ("excluye", "requiere")


class _Audited:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class _Observed:
    observations: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    observation_codes: Mapped[list[str]] = mapped_column(ARRAY(String(10)), nullable=False, server_default=text("'{}'"))


class ArticlePart(_Audited, _Observed, Base):
    __tablename__ = "article_part"
    __table_args__ = (
        CheckConstraint("source IN ('manual', 'seed', 'import')", name="ck_article_part_source"),
        Index("ix_article_part_parent", "parent_article_id"),
        Index("ix_article_part_part", "part_article_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parent_article_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("article.id", ondelete="CASCADE"), nullable=False)
    # Text as given; the screen checks them (like CO / AL).
    cop: Mapped[str] = mapped_column(String, nullable=False)
    alp: Mapped[str] = mapped_column(String, nullable=False)
    part_article_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("article.id", ondelete="SET NULL"), nullable=True)
    article_reference_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("article_reference.id", ondelete="SET NULL"), nullable=True
    )
    part_name: Mapped[str | None] = mapped_column(String, nullable=True)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, server_default="manual")
    link_notes: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))


class FunctionalProduct(_Audited, _Observed, Base):
    __tablename__ = "functional_product"
    __table_args__ = (
        CheckConstraint("source IN ('manual', 'seed', 'import', 'copia')", name="ck_functional_product_source"),
        Index("ix_functional_product_material", "material_id"),
        Index("ix_functional_product_article", "article_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    material_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("material.id", ondelete="CASCADE"), nullable=False)
    designation: Mapped[str] = mapped_column(String, nullable=False)
    pol_code: Mapped[str | None] = mapped_column(String, nullable=True)
    nae: Mapped[str | None] = mapped_column(String, nullable=True)
    noc: Mapped[str | None] = mapped_column(String, nullable=True)
    article_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("article.id", ondelete="SET NULL"), nullable=True)
    supply_unit: Mapped[str | None] = mapped_column(String, nullable=True)
    # None: in bulk ("N/A" in the file, as the kerosene of the NT's example).
    quantity: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    unit: Mapped[str | None] = mapped_column(String, nullable=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, server_default="manual")


class ExtraFunction(_Audited, Base):
    __tablename__ = "extra_function"
    __table_args__ = (
        CheckConstraint("source IN ('manual', 'seed', 'import', 'copia')", name="ck_extra_function_source"),
        Index("ix_extra_function_position", "position_id"),
        Index("ix_extra_function_material", "material_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    material_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("material.id", ondelete="CASCADE"), nullable=False)
    position_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("physical_position.id", ondelete="CASCADE"), nullable=False)
    sns: Mapped[str] = mapped_column(String, nullable=False)
    # A code of the reference table CRITERIO_MULTIFUNCION (configurable).
    criterion: Mapped[str] = mapped_column(String, nullable=False)
    comment: Mapped[str | None] = mapped_column(String, nullable=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, server_default="manual")


class Incompatibility(_Audited, _Observed, Base):
    __tablename__ = "incompatibility"
    __table_args__ = (
        CheckConstraint("kind IN ('excluye', 'requiere')", name="ck_incompatibility_kind"),
        CheckConstraint("row_a_id <> row_b_id", name="ck_incompatibility_distinct"),
        CheckConstraint("source IN ('manual', 'seed', 'import', 'copia')", name="ck_incompatibility_source"),
        Index("ix_incompatibility_material", "material_id"),
        Index("ix_incompatibility_a", "row_a_id"),
        Index("ix_incompatibility_b", "row_b_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    material_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("material.id", ondelete="CASCADE"), nullable=False)
    row_a_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("physical_position.id", ondelete="CASCADE"), nullable=False)
    row_b_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("physical_position.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False, server_default="manual")
