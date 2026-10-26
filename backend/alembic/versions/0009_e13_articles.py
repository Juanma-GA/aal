"""E13 flecos of the articles:

- The article's field columns lose their length (text, numeric): the
  definition's length and decimals are the validation's, and the admin
  corrects them in Ajustes (article_field_definition gets its version, who
  edited it and `edited_by_admin`, which a seed reload respects).
- vaUsoArt (field 56, coste €/hora) goes from 2,2 (at most 0,99) to 5,2, and
  caVoluArt (field 46) from 6 to 8 digits, as the MAR06 guide says (its
  "tamaño" counts the comma; ours, the digits: peso, largo, ancho and alto
  are already 7,2 = the guide's 8).
- article_reference (NT §9.1.6, one NOC with several P/N): the P/N + NCAGE
  of every article becomes its principal reference, and the columns go.
- article_revalidation: the background runs of the AR rules.

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-26

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# column -> its 0008 type (for the downgrade).
TEXT_COLUMNS = {
    "nombre": 40, "grupo_estructural": 1, "codigo_seguridad": 1, "reparable": 1, "consumible": 1, "unidad_suministro": 2,
    "control_unitario": 1, "documentacion_adjunta": 1, "unidad_peso": 2, "unidad_longitud": 2, "unidad_volumen": 2,
    "codigo_control_unitario": 1, "control_vida": 1, "escalon_1": 1, "escalon_2": 1, "escalon_3": 1, "escalon_4": 1,
    "control_configuracion": 1, "mantenimiento_preventivo": 1, "codigo_pol": 6,
}
NUMERIC_COLUMNS = {"precio_estandar": (9, 2), "peso": (7, 2), "largo": (7, 2), "ancho": (7, 2), "alto": (7, 2), "volumen": (6, 0), "coste_uso": (2, 2)}
# prisma code -> (old length, new length).
LENGTHS = {"vaUsoArt": (2, 5), "caVoluArt": (6, 8)}


def upgrade() -> None:
    op.add_column("article_field_definition", sa.Column("edited_by_admin", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("article_field_definition", sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")))
    op.add_column("article_field_definition", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "article_field_definition",
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True),
    )
    for code, (old, new) in LENGTHS.items():
        op.execute(
            sa.text("UPDATE article_field_definition SET length = :new WHERE prisma_code = :code AND length = :old").bindparams(new=new, code=code, old=old)
        )

    for column in TEXT_COLUMNS:
        op.alter_column("article", column, type_=sa.String(), existing_nullable=column != "nombre")
    for column in NUMERIC_COLUMNS:
        op.alter_column("article", column, type_=sa.Numeric(), existing_nullable=True)
    op.alter_column("article_life_control", "unit_code", type_=sa.String(), existing_nullable=True)
    op.alter_column("article_life_control", "quantity", type_=sa.Numeric(), existing_nullable=True)

    op.create_table(
        "article_reference",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("article_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("article.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("pn", sa.String(32), nullable=False),
        sa.Column("ncage", sa.String(5), nullable=True),
        sa.Column("principal", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("origin", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.CheckConstraint("ncage IS NULL OR ncage ~ '^[0-9A-Z]{5}$'", name="ck_article_reference_ncage"),
        sa.CheckConstraint("origin IN ('manual', 'importacion', 'confunfis', 'migracion')", name="ck_article_reference_origin"),
    )
    op.create_index(
        "uq_article_reference_pn_ncage", "article_reference", ["pn", "ncage"], unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND ncage IS NOT NULL"),
    )
    op.create_index(
        "uq_article_reference_principal", "article_reference", ["article_id"], unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND principal"),
    )
    op.create_index("ix_article_reference_pn", "article_reference", ["pn"])

    bind = op.get_bind()
    orphans = bind.execute(sa.text("SELECT count(*) FROM article WHERE pn IS NULL AND ncage IS NOT NULL")).scalar()
    if orphans:
        # A reference needs its P/N: say it rather than lose the NCAGE (HR7).
        raise RuntimeError(f"{orphans} article(s) have an NCAGE without P/N: give them their P/N (or remove the NCAGE) and migrate again")
    op.execute(
        """
        INSERT INTO article_reference (id, article_id, pn, ncage, principal, origin, created_at, created_by, updated_at, updated_by, deleted_at, version)
        SELECT gen_random_uuid(), id, pn, ncage, true, 'migracion', created_at, created_by, updated_at, updated_by, deleted_at, 1
        FROM article WHERE pn IS NOT NULL
        """
    )
    op.drop_index("uq_article_pn_ncage", table_name="article")
    op.drop_constraint("ck_article_ncage", "article", type_="check")
    op.drop_column("article", "pn")
    op.drop_column("article", "ncage")

    op.create_table(
        "article_revalidation",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("reason", sa.String(30), nullable=False),
        sa.Column("detail", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("report", postgresql.JSONB(), nullable=True),
        sa.Column("error_code", sa.String(60), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("reason IN ('manual', 'reference_table', 'field_definition')", name="ck_article_revalidation_reason"),
        sa.CheckConstraint("status IN ('queued', 'running', 'done', 'failed')", name="ck_article_revalidation_status"),
    )


def downgrade() -> None:
    op.drop_table("article_revalidation")
    op.add_column("article", sa.Column("pn", sa.String(32), nullable=True))
    op.add_column("article", sa.Column("ncage", sa.String(5), nullable=True))
    # Only the principal reference fits back in the article.
    op.execute(
        """
        UPDATE article a SET pn = r.pn, ncage = r.ncage
        FROM article_reference r WHERE r.article_id = a.id AND r.principal AND r.deleted_at IS NULL
        """
    )
    op.create_check_constraint("ck_article_ncage", "article", "ncage IS NULL OR ncage ~ '^[0-9A-Z]{5}$'")
    op.create_index(
        "uq_article_pn_ncage", "article", ["pn", "ncage"], unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND pn IS NOT NULL AND ncage IS NOT NULL"),
    )
    op.drop_table("article_reference")

    op.alter_column("article_life_control", "quantity", type_=sa.Numeric(8, 0), existing_nullable=True)
    op.alter_column("article_life_control", "unit_code", type_=sa.String(2), existing_nullable=True)
    for column, (precision, scale) in NUMERIC_COLUMNS.items():
        op.alter_column("article", column, type_=sa.Numeric(precision, scale), existing_nullable=True)
    for column, length in TEXT_COLUMNS.items():
        op.alter_column("article", column, type_=sa.String(length), existing_nullable=column != "nombre")

    for code, (old, new) in LENGTHS.items():
        op.execute(
            sa.text("UPDATE article_field_definition SET length = :old WHERE prisma_code = :code AND length = :new").bindparams(new=new, code=code, old=old)
        )
    op.drop_column("article_field_definition", "updated_by")
    op.drop_column("article_field_definition", "updated_at")
    op.drop_column("article_field_definition", "version")
    op.drop_column("article_field_definition", "edited_by_admin")
