"""E16: the module "Validación NT 10/17" is turned on (status disponible and
its route: the material's validation page), as
app/seeds/module_catalog_seed.yaml says for a new database.

Revision ID: 0017
Revises: 0016
"""

import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None

MODULES = {"validacion": "/materiales/:materialId/validacion"}


def upgrade() -> None:
    for code, route in MODULES.items():
        op.execute(
            sa.text("UPDATE module_catalog SET status = 'disponible', route = :route, version = version + 1 WHERE code = :code").bindparams(route=route, code=code)
        )


def downgrade() -> None:
    for code in MODULES:
        op.execute(sa.text("UPDATE module_catalog SET status = 'planificado', route = NULL, version = version + 1 WHERE code = :code").bindparams(code=code))
