"""E14: the modules "Tabla de partes" and "Productos funcionales" are turned
on (status disponible and their route: the CONFUNFIS page on its tab), as
app/seeds/module_catalog_seed.yaml says for a new database.

Revision ID: 0012
Revises: 0011
"""

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

MODULES = {"tabla-partes": "/materiales/:materialId/confunfis/partes", "productos-funcionales": "/materiales/:materialId/confunfis/productos"}


def upgrade() -> None:
    for code, route in MODULES.items():
        op.execute(
            sa.text("UPDATE module_catalog SET status = 'disponible', route = :route, version = version + 1 WHERE code = :code").bindparams(route=route, code=code)
        )


def downgrade() -> None:
    for code in MODULES:
        op.execute(sa.text("UPDATE module_catalog SET status = 'planificado', route = NULL, version = version + 1 WHERE code = :code").bindparams(code=code))
