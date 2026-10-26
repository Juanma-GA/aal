"""The article (E12, RF-04): the physical part identified by its NOC (or
NPC), P/N and NCAGE. Global (D16): one record for every CUF that uses it.

Its basic data are the 30 fields of the SIGLE Fichero Carga
(article_field_definition, E03). Each has a typed column here, named after
the field and listed in FIELD_COLUMNS (PRISMA code -> column), except the
life control: SIGLE allows up to three pairs (code D114 + quantity), so
they live in article_life_control and the Fichero Carga's cdUniVidaA /
caVidaArt are its first pair. The column has the field's type (text or
number) but no length (E13, migration 0009): the length and decimals are
the definition's, which the admin corrects in Ajustes without code, and
every write goes through the validation that reads them
(app/services/article_fields.py).

Its P/N + NCAGE are its references (E13, NT §9.1.6: one NOC, several
P/N): `article_reference`, 0..n per article, one of them the principal --
what the Fichero Carga's world calls "the" P/N of the article (`pn`,
`ncage` here).
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

NAME_ORIGINS = ("coloquial", "aprobado", "comercial")
# Where a reference came from: typed in, an import, a CONFUNFIS row (E13),
# the E12 article's own P/N + NCAGE (migration 0009).
REFERENCE_ORIGINS = ("manual", "importacion", "confunfis", "migracion")
# The life control pairs SIGLE allows.
MAX_LIFE_CONTROLS = 3
# The Fichero Carga's pair of the life control (the first one).
LIFE_CODE_FIELD, LIFE_QUANTITY_FIELD = "cdUniVidaA", "caVidaArt"

# PRISMA code of each field -> its column in `article`.
FIELD_COLUMNS: dict[str, str] = {
    "cdART": "noc",
    "NomArt": "nombre",
    "cdConjRep": "grupo_estructural",
    "cdSegArt": "codigo_seguridad",
    "snRepaArt": "reparable",
    "snConsuArt": "consumible",
    "cdUsumExtrArt": "unidad_suministro",
    "snCtrlUniArt": "control_unitario",
    "imEstdArt": "precio_estandar",
    "snDocuAdjUArt": "documentacion_adjunta",
    "caPesoArt": "peso",
    "cdUnidPesoArt": "unidad_peso",
    "caLargoArt": "largo",
    "caAnchoArt": "ancho",
    "caAltoArt": "alto",
    "cdUnidLongArt": "unidad_longitud",
    "caVoluArt": "volumen",
    "cdUnidVoluArt": "unidad_volumen",
    "cdCtrlUniArt": "codigo_control_unitario",
    "snCtrlVidaArt": "control_vida",
    "snMtN1Art": "escalon_1",
    "snMtN2Art": "escalon_2",
    "snMtN3Art": "escalon_3",
    "snMtN4Art": "escalon_4",
    "vaUsoArt": "coste_uso",
    "snCnfgArt": "control_configuracion",
    "snMtPreArt": "mantenimiento_preventivo",
    "cdPolEl": "codigo_pol",
}


class Article(Base):
    __tablename__ = "article"
    __table_args__ = (
        CheckConstraint("noc IS NULL OR noc ~ '^[0-9A-Z]{13}$'", name="ck_article_noc"),
        CheckConstraint("origen_nombre IN ('coloquial', 'aprobado', 'comercial')", name="ck_article_origen_nombre"),
        CheckConstraint("origin IN ('maestro', 'confunfis')", name="ck_article_origin"),
        # Unique among the live articles: the NOC (P/N + NCAGE: article_reference).
        Index("uq_article_noc", "noc", unique=True, postgresql_where=text("deleted_at IS NULL AND noc IS NOT NULL")),
        Index("ix_article_finding_codes", "finding_codes", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    noc: Mapped[str | None] = mapped_column(String(13), nullable=True)
    nombre: Mapped[str] = mapped_column(String, nullable=False)
    origen_nombre: Mapped[str] = mapped_column(String(20), nullable=False, server_default="coloquial")
    # Where it was born (E13): the master (the screen, an import), or a
    # CONFUNFIS row that found no article -- a provisional one to complete.
    origin: Mapped[str] = mapped_column(String(20), nullable=False, server_default="maestro")
    grupo_estructural: Mapped[str | None] = mapped_column(String, nullable=True)
    codigo_seguridad: Mapped[str | None] = mapped_column(String, nullable=True)
    reparable: Mapped[str | None] = mapped_column(String, nullable=True)
    consumible: Mapped[str | None] = mapped_column(String, nullable=True)
    unidad_suministro: Mapped[str | None] = mapped_column(String, nullable=True)
    control_unitario: Mapped[str | None] = mapped_column(String, nullable=True)
    precio_estandar: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    documentacion_adjunta: Mapped[str | None] = mapped_column(String, nullable=True)
    peso: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    unidad_peso: Mapped[str | None] = mapped_column(String, nullable=True)
    largo: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    ancho: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    alto: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    unidad_longitud: Mapped[str | None] = mapped_column(String, nullable=True)
    volumen: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    unidad_volumen: Mapped[str | None] = mapped_column(String, nullable=True)
    codigo_control_unitario: Mapped[str | None] = mapped_column(String, nullable=True)
    control_vida: Mapped[str | None] = mapped_column(String, nullable=True)
    escalon_1: Mapped[str | None] = mapped_column(String, nullable=True)
    escalon_2: Mapped[str | None] = mapped_column(String, nullable=True)
    escalon_3: Mapped[str | None] = mapped_column(String, nullable=True)
    escalon_4: Mapped[str | None] = mapped_column(String, nullable=True)
    coste_uso: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    control_configuracion: Mapped[str | None] = mapped_column(String, nullable=True)
    mantenimiento_preventivo: Mapped[str | None] = mapped_column(String, nullable=True)
    codigo_pol: Mapped[str | None] = mapped_column(String, nullable=True)
    # The AR rules it breaks, as last checked (app/validacion/articulos.py):
    # the findings, and their codes for the list's filter.
    findings: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    finding_codes: Mapped[list[str]] = mapped_column(ARRAY(String(10)), nullable=False, server_default=text("'{}'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))

    life_controls: Mapped[list["ArticleLifeControl"]] = relationship(
        order_by="ArticleLifeControl.position", cascade="all, delete-orphan", lazy="selectin"
    )
    # Every reference, the removed ones too (HR9); `live_references` are the others.
    references: Mapped[list["ArticleReference"]] = relationship(
        order_by="ArticleReference.created_at", cascade="all, delete-orphan", lazy="selectin", back_populates="article"
    )

    @property
    def live_references(self) -> list["ArticleReference"]:
        """The principal first, then in the order they were added."""
        live = [r for r in self.references if r.deleted_at is None]
        return sorted(live, key=lambda r: not r.principal)

    @property
    def principal_reference(self) -> "ArticleReference | None":
        return next((r for r in self.references if r.deleted_at is None and r.principal), None)

    @property
    def pn(self) -> str | None:
        r = self.principal_reference
        return r.pn if r else None

    @property
    def ncage(self) -> str | None:
        r = self.principal_reference
        return r.ncage if r else None


class ArticleLifeControl(Base):
    """One of the (up to three) life controls of an article: a D114 code
    and its quantity (MAR06 fields 64 and 65)."""

    __tablename__ = "article_life_control"
    __table_args__ = (CheckConstraint(f"position BETWEEN 1 AND {MAX_LIFE_CONTROLS}", name="ck_article_life_control_position"),)

    article_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("article.id", ondelete="CASCADE"), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, primary_key=True)
    unit_code: Mapped[str | None] = mapped_column(String, nullable=True)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)


class ArticleReference(Base):
    """A P/N + NCAGE of an article (E13, NT §9.1.6). (P/N, NCAGE) is unique
    among the live references when both exist; an article has at most one
    live principal. Removed logically (HR9)."""

    __tablename__ = "article_reference"
    __table_args__ = (
        CheckConstraint("ncage IS NULL OR ncage ~ '^[0-9A-Z]{5}$'", name="ck_article_reference_ncage"),
        CheckConstraint("origin IN ('manual', 'importacion', 'confunfis', 'migracion')", name="ck_article_reference_origin"),
        Index(
            "uq_article_reference_pn_ncage", "pn", "ncage", unique=True,
            postgresql_where=text("deleted_at IS NULL AND ncage IS NOT NULL"),
        ),
        Index("uq_article_reference_principal", "article_id", unique=True, postgresql_where=text("deleted_at IS NULL AND principal")),
        Index("ix_article_reference_pn", "pn"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    article_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("article.id", ondelete="CASCADE"), nullable=False, index=True)
    pn: Mapped[str] = mapped_column(String(32), nullable=False)
    ncage: Mapped[str | None] = mapped_column(String(5), nullable=True)
    principal: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    origin: Mapped[str] = mapped_column(String(20), nullable=False, server_default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))

    article: Mapped[Article] = relationship(back_populates="references")


# manual (the button in Artículos), reference_table / field_definition
# (after an import or an edit of one, E13); queued -> running -> done | failed.
REVALIDATION_REASONS = ("manual", "reference_table", "field_definition")


class ArticleRevalidation(Base):
    """A run of the AR rules over every live article, in the background
    (E13): how many findings each rule gained and lost. Postgres is the
    only record of where it stands (HR1)."""

    __tablename__ = "article_revalidation"
    __table_args__ = (
        CheckConstraint("reason IN ('manual', 'reference_table', 'field_definition')", name="ck_article_revalidation_reason"),
        CheckConstraint("status IN ('queued', 'running', 'done', 'failed')", name="ck_article_revalidation_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reason: Mapped[str] = mapped_column(String(30), nullable=False)
    # What triggered it: {"table": "D112"} or {"field": "vaUsoArt"}.
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="queued")
    # {"articles": n, "changed": n, "by_rule": {"AR-001": {"appeared": n, "disappeared": n}, ...}}
    report: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(60), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
