"""E15: the reference table UNIDAD_MEDIDA_PF (unit of measure of the
functional products, with its D112 equivalence), loaded from the seed: the
Anexo XI writes L or KG, the D112 codes are LI and KG.

Revision ID: 0013
Revises: 0012
"""

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.services.reference_seed import load_reference_tables

    load_reference_tables(op.get_bind())


def downgrade() -> None:
    op.execute("DELETE FROM reference_value WHERE table_code = 'UNIDAD_MEDIDA_PF'")
    op.execute("DELETE FROM reference_table WHERE code = 'UNIDAD_MEDIDA_PF'")
