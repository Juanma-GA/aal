"""Articles (E12, RF-04): the single article master (article) with a typed
column per field of the SIGLE Fichero Carga, its up to three life controls
(article_life_control), and the article fields' Fichero Carga header, S/N
values and MAR06 help (article_field_definition.header, allowed_values,
help), loaded from the seeds by app/services/reference_seed.py. The module
"Artículos — datos básicos" is turned on at /articulos.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-26

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MODULE = "articulos"
ROUTE = "/articulos"


def _yes_no(name: str) -> sa.Column:
    return sa.Column(name, sa.String(1), nullable=True)


def upgrade() -> None:
    op.add_column("article_field_definition", sa.Column("header", sa.String(200), nullable=True))
    op.add_column("article_field_definition", sa.Column("allowed_values", postgresql.JSONB(), nullable=True))
    op.add_column("article_field_definition", sa.Column("help", postgresql.JSONB(), nullable=True))
    op.create_table(
        "article",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("noc", sa.String(13), nullable=True),
        sa.Column("pn", sa.String(32), nullable=True),
        sa.Column("ncage", sa.String(5), nullable=True),
        sa.Column("nombre", sa.String(40), nullable=False),
        sa.Column("origen_nombre", sa.String(20), nullable=False, server_default="coloquial"),
        sa.Column("grupo_estructural", sa.String(1), nullable=True),
        sa.Column("codigo_seguridad", sa.String(1), nullable=True),
        _yes_no("reparable"),
        _yes_no("consumible"),
        sa.Column("unidad_suministro", sa.String(2), nullable=True),
        _yes_no("control_unitario"),
        sa.Column("precio_estandar", sa.Numeric(9, 2), nullable=True),
        _yes_no("documentacion_adjunta"),
        sa.Column("peso", sa.Numeric(7, 2), nullable=True),
        sa.Column("unidad_peso", sa.String(2), nullable=True),
        sa.Column("largo", sa.Numeric(7, 2), nullable=True),
        sa.Column("ancho", sa.Numeric(7, 2), nullable=True),
        sa.Column("alto", sa.Numeric(7, 2), nullable=True),
        sa.Column("unidad_longitud", sa.String(2), nullable=True),
        sa.Column("volumen", sa.Numeric(6, 0), nullable=True),
        sa.Column("unidad_volumen", sa.String(2), nullable=True),
        sa.Column("codigo_control_unitario", sa.String(1), nullable=True),
        _yes_no("control_vida"),
        _yes_no("escalon_1"),
        _yes_no("escalon_2"),
        _yes_no("escalon_3"),
        _yes_no("escalon_4"),
        sa.Column("coste_uso", sa.Numeric(2, 2), nullable=True),
        _yes_no("control_configuracion"),
        _yes_no("mantenimiento_preventivo"),
        sa.Column("codigo_pol", sa.String(6), nullable=True),
        sa.Column("findings", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("finding_codes", postgresql.ARRAY(sa.String(10)), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.CheckConstraint("noc IS NULL OR noc ~ '^[0-9A-Z]{13}$'", name="ck_article_noc"),
        sa.CheckConstraint("ncage IS NULL OR ncage ~ '^[0-9A-Z]{5}$'", name="ck_article_ncage"),
        sa.CheckConstraint("origen_nombre IN ('coloquial', 'aprobado', 'comercial')", name="ck_article_origen_nombre"),
    )
    op.create_index("uq_article_noc", "article", ["noc"], unique=True, postgresql_where=sa.text("deleted_at IS NULL AND noc IS NOT NULL"))
    op.create_index(
        "uq_article_pn_ncage", "article", ["pn", "ncage"], unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND pn IS NOT NULL AND ncage IS NOT NULL"),
    )
    op.create_index("ix_article_finding_codes", "article", ["finding_codes"], postgresql_using="gin")
    op.create_table(
        "article_life_control",
        sa.Column("article_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("article.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("position", sa.Integer(), primary_key=True),
        sa.Column("unit_code", sa.String(2), nullable=True),
        sa.Column("quantity", sa.Numeric(8, 0), nullable=True),
        sa.CheckConstraint("position BETWEEN 1 AND 3", name="ck_article_life_control_position"),
    )

    from app.services.reference_seed import load_article_field_extras

    load_article_field_extras(op.get_bind())
    op.execute(
        sa.text("UPDATE module_catalog SET status = 'disponible', route = :route, version = version + 1 WHERE code = :code").bindparams(
            route=ROUTE, code=MODULE
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text("UPDATE module_catalog SET status = 'planificado', route = NULL, version = version + 1 WHERE code = :code").bindparams(code=MODULE)
    )
    op.drop_table("article_life_control")
    op.drop_index("ix_article_finding_codes", table_name="article")
    op.drop_index("uq_article_pn_ncage", table_name="article")
    op.drop_index("uq_article_noc", table_name="article")
    op.drop_table("article")
    op.drop_column("article_field_definition", "help")
    op.drop_column("article_field_definition", "allowed_values")
    op.drop_column("article_field_definition", "header")
