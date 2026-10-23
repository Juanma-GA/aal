import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Material(Base):
    """A material = its CUF (D12), the container of everything else. E01
    keeps only what roles need; E11 completes it (subcategories, normalized
    configuration, copy from another CUF).

    The NOC is optional until the CUF is catalogued, and unique among the
    materials not deleted.
    """

    __tablename__ = "material"
    __table_args__ = (
        Index(
            "uq_material_noc_active",
            "noc",
            unique=True,
            postgresql_where=text("noc IS NOT NULL AND deleted_at IS NULL"),
        ),
        CheckConstraint("grupo_clase IS NULL OR grupo_clase ~ '^[0-9]{4}$'", name="ck_material_grupo_clase"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    noc: Mapped[str | None] = mapped_column(String(13), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    part_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ncage: Mapped[str | None] = mapped_column(String(5), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("app_user.id"), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    # E11: the catalog version the CUF works with (the active one when it
    # is created; only an admin changes it), its Grupo-Clase (informative,
    # four digits) and the CUF it was copied from (a variant).
    catalog_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("catalog_version.id", ondelete="SET NULL"), nullable=True
    )
    grupo_clase: Mapped[str | None] = mapped_column(String(4), nullable=True)
    copied_from_material_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("material.id", ondelete="SET NULL"), nullable=True
    )


class MaterialSubcategoryLink(Base):
    """A subcategory of material the CUF includes (NT §8): its normalized
    configuration is the union of their SNS."""

    __tablename__ = "material_subcategory_link"

    material_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("material.id", ondelete="CASCADE"), primary_key=True)
    subcategory_code: Mapped[str] = mapped_column(String(4), ForeignKey("material_subcategory.code"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


# borrador -> enviada -> aceptada | rechazada (NT §9.1.1).
SNS_REQUEST_STATES = ("borrador", "enviada", "aceptada", "rechazada")


class SnsRequest(Base):
    """A request for a new SNS (NT §9.1.1): the function of a component of
    the CUF is not in its normalized configuration. Drafted and sent by
    whoever edits the material; an admin accepts or rejects it with an
    answer. A draft may be discarded (soft delete, HR9)."""

    __tablename__ = "sns_request"
    __table_args__ = (
        CheckConstraint("state IN ('borrador', 'enviada', 'aceptada', 'rechazada')", name="ck_sns_request_state"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    material_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("material.id"), nullable=False, index=True)
    proposed_sns: Mapped[str | None] = mapped_column(String(6), nullable=True)
    parent_sns: Mapped[str | None] = mapped_column(String(6), nullable=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    function: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False, server_default="borrador")
    response: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
