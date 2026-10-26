"""E15b: AR-008 on the articles already stored. Until E15b only the Fichero
Carga / Maestro AAL import and the article form applied it; an article
created from the CONFUNFIS or a parts table kept an empty security code, so
exporting the Maestro AAL and importing it back showed it "modified" (empty
-> U). Each article corrected gets its version bumped and an audit row,
action article.autocorrected, with the correction. Its findings do not
change (field 19 is "Recomendado" and U is a D106 code).

Revision ID: 0015
Revises: 0014
"""

import json

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None

# The AR-008 rule (app/validacion/articulos.py RULES["AR-008"]), as it was on
# this date: a migration must not change if the rule's parameters change.
FIELD, COLUMN, DEFAULT = "cdSegArt", "codigo_seguridad", "U"


def upgrade() -> None:
    # Empty as the rule sees it (app/validacion/articulos.py _empty): NULL or "".
    # One statement: the old value is read, the article corrected and audited with what it had.
    op.get_bind().execute(
        sa.text(
            f"""
            WITH old AS (
                SELECT id, {COLUMN} AS value FROM article
                WHERE deleted_at IS NULL AND ({COLUMN} IS NULL OR {COLUMN} = '') FOR UPDATE
            ), fixed AS (
                UPDATE article SET {COLUMN} = :value, version = version + 1, updated_at = now()
                FROM old WHERE article.id = old.id RETURNING article.id, old.value
            )
            INSERT INTO audit_log (id, created_at, user_id, action, entity_type, entity_id, before, after)
            SELECT gen_random_uuid(), now(), NULL, 'article.autocorrected', 'article', fixed.id::text,
                   jsonb_build_object('{COLUMN}', fixed.value), CAST(:after AS jsonb)
            FROM fixed
            """
        ),
        # import_origin, as audit.origin() writes it: "origin" is the article's own field.
        {"value": DEFAULT, "after": json.dumps({"corrections": [{"code": "AR-008", "field": FIELD, "value": DEFAULT}], "import_origin": {"migration": "0015"}})},
    )
    # The findings do not change while field 19 is "Recomendado" (the seed) and U is a D106 code; had an admin
    # made it Obligatorio (Ajustes -> Campos del artículo), "Revalidar todos los artículos" refreshes them.


def downgrade() -> None:
    # A correction is not undone: the value is the one the rule gives, and the audit keeps what was there.
    pass
