"""The article (E12, RF-04): the physical part identified by its NOC (or
NPC), P/N and NCAGE. Global (D16): one record for every CUF that uses it.

Its basic data are the 30 fields of the SIGLE Fichero Carga
(article_field_definition, E03). Each has a typed column here, named after
the field and listed in FIELD_COLUMNS (PRISMA code -> column), except the
life control: SIGLE allows up to three pairs (code D114 + quantity), so
they live in article_life_control and the Fichero Carga's cdUniVidaA /
caVidaArt are its first pair. Types and lengths are those of the field's
definition (migration 0008); the validation reads them from there too.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

NAME_ORIGINS = ("coloquial", "aprobado", "comercial")
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
        CheckConstraint("ncage IS NULL OR ncage ~ '^[0-9A-Z]{5}$'", name="ck_article_ncage"),
        CheckConstraint("origen_nombre IN ('coloquial', 'aprobado', 'comercial')", name="ck_article_origen_nombre"),
        # Unique among the live articles: the NOC, and P/N + NCAGE when both exist.
        Index("uq_article_noc", "noc", unique=True, postgresql_where=text("deleted_at IS NULL AND noc IS NOT NULL")),
        Index(
            "uq_article_pn_ncage", "pn", "ncage", unique=True,
            postgresql_where=text("deleted_at IS NULL AND pn IS NOT NULL AND ncage IS NOT NULL"),
        ),
        Index("ix_article_finding_codes", "finding_codes", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    noc: Mapped[str | None] = mapped_column(String(13), nullable=True)
    pn: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ncage: Mapped[str | None] = mapped_column(String(5), nullable=True)
    nombre: Mapped[str] = mapped_column(String(40), nullable=False)
    origen_nombre: Mapped[str] = mapped_column(String(20), nullable=False, server_default="coloquial")
    grupo_estructural: Mapped[str | None] = mapped_column(String(1), nullable=True)
    codigo_seguridad: Mapped[str | None] = mapped_column(String(1), nullable=True)
    reparable: Mapped[str | None] = mapped_column(String(1), nullable=True)
    consumible: Mapped[str | None] = mapped_column(String(1), nullable=True)
    unidad_suministro: Mapped[str | None] = mapped_column(String(2), nullable=True)
    control_unitario: Mapped[str | None] = mapped_column(String(1), nullable=True)
    precio_estandar: Mapped[Decimal | None] = mapped_column(Numeric(9, 2), nullable=True)
    documentacion_adjunta: Mapped[str | None] = mapped_column(String(1), nullable=True)
    peso: Mapped[Decimal | None] = mapped_column(Numeric(7, 2), nullable=True)
    unidad_peso: Mapped[str | None] = mapped_column(String(2), nullable=True)
    largo: Mapped[Decimal | None] = mapped_column(Numeric(7, 2), nullable=True)
    ancho: Mapped[Decimal | None] = mapped_column(Numeric(7, 2), nullable=True)
    alto: Mapped[Decimal | None] = mapped_column(Numeric(7, 2), nullable=True)
    unidad_longitud: Mapped[str | None] = mapped_column(String(2), nullable=True)
    volumen: Mapped[Decimal | None] = mapped_column(Numeric(6, 0), nullable=True)
    unidad_volumen: Mapped[str | None] = mapped_column(String(2), nullable=True)
    codigo_control_unitario: Mapped[str | None] = mapped_column(String(1), nullable=True)
    control_vida: Mapped[str | None] = mapped_column(String(1), nullable=True)
    escalon_1: Mapped[str | None] = mapped_column(String(1), nullable=True)
    escalon_2: Mapped[str | None] = mapped_column(String(1), nullable=True)
    escalon_3: Mapped[str | None] = mapped_column(String(1), nullable=True)
    escalon_4: Mapped[str | None] = mapped_column(String(1), nullable=True)
    coste_uso: Mapped[Decimal | None] = mapped_column(Numeric(2, 2), nullable=True)
    control_configuracion: Mapped[str | None] = mapped_column(String(1), nullable=True)
    mantenimiento_preventivo: Mapped[str | None] = mapped_column(String(1), nullable=True)
    codigo_pol: Mapped[str | None] = mapped_column(String(6), nullable=True)
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


class ArticleLifeControl(Base):
    """One of the (up to three) life controls of an article: a D114 code
    and its quantity (MAR06 fields 64 and 65)."""

    __tablename__ = "article_life_control"
    __table_args__ = (CheckConstraint(f"position BETWEEN 1 AND {MAX_LIFE_CONTROLS}", name="ck_article_life_control_position"),)

    article_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("article.id", ondelete="CASCADE"), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, primary_key=True)
    unit_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(8, 0), nullable=True)
