"""E15: the CONFUNFIS records take the time of their own insert, not of the
transaction's start (clock_timestamp() instead of now()). Records with the
same key are matched in the order they were created (the book import, E15),
and one import or seed creates them all in a single transaction: with now()
they tied and the order fell to the random id.

Revision ID: 0014
Revises: 0013
"""

from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

TABLES = ("physical_position", "functional_product", "extra_function", "incompatibility", "article_part")


def upgrade() -> None:
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN created_at SET DEFAULT clock_timestamp()")


def downgrade() -> None:
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN created_at SET DEFAULT now()")
