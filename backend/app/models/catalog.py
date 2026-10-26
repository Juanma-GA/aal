import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

SNS_LENGTH = 6


class CatalogVersion(Base):
    """One imported CONF_FUN file (E10, NT 10/17 Anexo II): the normalized
    functional configuration as JIMALE published it. Only one is active;
    the older ones are kept for good (HR9), with their warnings."""

    __tablename__ = "catalog_version"
    __table_args__ = (
        Index("uq_catalog_version_active", "is_active", unique=True, postgresql_where=text("is_active")),
        CheckConstraint("NOT (is_active AND deleted_at IS NOT NULL)", name="ck_catalog_version_active_not_deleted"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    number: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    # rows, sns, categories, subcategories, cn_001..cn_006...
    counts: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    # The CN-001..CN-006 warnings of the import (the issues of its report).
    warnings: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    notes: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    # Deleted by an admin (E12): out of every list, selector and diff; kept (HR9).
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MaterialCategory(Base):
    """A material category (two digits, "06" Plataformas terrestres).
    Shared by every catalog version and reconciled on import: never
    deleted, its name follows the latest version."""

    __tablename__ = "material_category"

    code: Mapped[str] = mapped_column(String(2), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)


class MaterialSubcategory(Base):
    """A subcategory ("0601" Vehículos de ruedas): category + its two
    digits. Like the categories, reconciled and never deleted (E11 links
    each CUF to its subcategories)."""

    __tablename__ = "material_subcategory"
    __table_args__ = (UniqueConstraint("category_code", "sub_code", name="uq_material_subcategory"),)

    code: Mapped[str] = mapped_column(String(4), primary_key=True)
    category_code: Mapped[str] = mapped_column(String(2), ForeignKey("material_category.code"), nullable=False)
    sub_code: Mapped[str] = mapped_column(String(2), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)


class SnsPosition(Base):
    """An SNS of a version: one per code, with its main name and
    description, the level and parent derived from the code (NT §6) and
    every level the file declared for it."""

    __tablename__ = "sns_position"
    __table_args__ = (
        UniqueConstraint("version_id", "sns", name="uq_sns_position"),
        Index("ix_sns_position_parent", "version_id", "parent_sns"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("catalog_version.id", ondelete="CASCADE"), nullable=False)
    sns: Mapped[str] = mapped_column(String(SNS_LENGTH), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    description_pending: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    level: Mapped[str] = mapped_column(String(20), nullable=False)
    parent_sns: Mapped[str | None] = mapped_column(String(SNS_LENGTH), nullable=True)
    declared_levels: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))


class SubcategorySns(Base):
    """One row of the file, as imported (the description repaired when it
    came split, CN-005): where an SNS appears, with which declared level
    and name. A row without category nor subcategory (CN-004) is kept with
    both empty. The export is rebuilt from these rows."""

    __tablename__ = "subcategory_sns"
    __table_args__ = (
        Index("ix_subcategory_sns_version_sub", "version_id", "subcategory_code", "sns"),
        Index("ix_subcategory_sns_version_sns", "version_id", "sns"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("catalog_version.id", ondelete="CASCADE"), nullable=False)
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    subcategory_code: Mapped[str | None] = mapped_column(String(4), ForeignKey("material_subcategory.code"), nullable=True)
    category_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    category_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    sub_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    subcategory_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    sns: Mapped[str] = mapped_column(String(SNS_LENGTH), nullable=False)
    declared_level: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    description_repaired: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))


class SnsExtraName(Base):
    """Another name of an SNS in a version: an ELEMENTO row (an extra
    denomination under a subconjunto) or a different name (CN-001)."""

    __tablename__ = "sns_extra_name"
    __table_args__ = (UniqueConstraint("version_id", "sns", "name", name="uq_sns_extra_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("catalog_version.id", ondelete="CASCADE"), nullable=False)
    sns: Mapped[str] = mapped_column(String(SNS_LENGTH), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    origin: Mapped[str] = mapped_column(String(20), nullable=False)
