"""E17: the permissions of the delivery, the baselines and the change
authorizations, in the matrix (D5: no role rule in code; the admin may
change them in Ajustes -> Roles y permisos):

- confunfis.entregar: "Exportar para entrega" (analista, revisor). The
  observer keeps "exportar", the working exports (with the BORRADOR sheet).
- baseline.crear (analista) and baseline.revisar (revisor): freezing a
  CUF's CONFUNFIS and approving or rejecting it (never its author).
- autorizacion.solicitar (analista) and autorizacion.aprobar (revisor):
  the change authorizations needed after a reviewed baseline.

Validating asks validacion.ejecutar (analista, revisor: in the matrix since
0002); reading the report, validacion.ver.

Revision ID: 0018
Revises: 0017
"""

import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None

PERMISSIONS = (
    ("confunfis.entregar", "confunfis", {"analista", "revisor"}),
    ("baseline.crear", "baseline", {"analista"}),
    ("baseline.revisar", "baseline", {"revisor"}),
    ("autorizacion.solicitar", "autorizacion", {"analista"}),
    ("autorizacion.aprobar", "autorizacion", {"revisor"}),
)


def upgrade() -> None:
    last = op.get_bind().execute(sa.text("SELECT coalesce(max(sort_order), 0) FROM permission")).scalar_one()
    for i, (code, area, roles) in enumerate(PERMISSIONS, start=1):
        op.execute(sa.text("INSERT INTO permission (code, area, sort_order) VALUES (:code, :area, :order) ON CONFLICT DO NOTHING")
                   .bindparams(code=code, area=area, order=last + i))
        for role in sorted(roles):
            op.execute(sa.text("INSERT INTO role_permission (role_code, permission_code) VALUES (:role, :code) ON CONFLICT DO NOTHING")
                       .bindparams(role=role, code=code))


def downgrade() -> None:
    for code, _area, _roles in PERMISSIONS:
        op.execute(sa.text("DELETE FROM permission WHERE code = :code").bindparams(code=code))
