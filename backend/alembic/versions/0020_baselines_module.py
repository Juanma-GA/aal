"""E17: the module "Baselines y cambios" (disponible, its route: the
material's baselines page), loaded from app/seeds/module_catalog_seed.yaml
as for a new database (load_catalog adds the new module and never touches
the status or route of the others).

Revision ID: 0020
Revises: 0019
"""

import sqlalchemy as sa
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.services.module_catalog import load_catalog

    load_catalog(op.get_bind())


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM module_requirement WHERE module_code = 'baselines'"))
    op.execute(sa.text("DELETE FROM module_catalog WHERE code = 'baselines'"))
