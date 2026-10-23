"""The demo materials (E10, D14): the five materials of
demo/LEEME_DATOS_DEMO.md §1 (VTL 4X4 TRAMONTANA and its relatives, all
invented), with the three development users assigned (analista, revisor,
observador). Never on a server (refused with ENVIRONMENT=production).

    python scripts/seed_demo_materials.py        (from backend/)

Idempotent: a material whose name already exists is not duplicated nor
changed, and a role already assigned is kept. The development users come
from scripts/seed_dev_data.py; one that does not exist is reported and
skipped.
"""

import asyncio
import sys

from _common import cancellable, utf8_output

from sqlalchemy import select

from app.core.config import get_settings
from app.db.base import async_session_factory, engine
from app.models import Material, User, UserMaterialRole
from app.services import audit

# demo/LEEME_DATOS_DEMO.md §1: name, NOC, P/N, NCAGE, description.
DEMO_MATERIALS = (
    (
        "VTL 4X4 TRAMONTANA",
        "232033X900001",
        "TRM-4X4-A",
        "DEMO1",
        "Vehículo táctico ligero 4x4 para transporte de personal y carga en cualquier terreno. Motor diésel de 6 cilindros "
        "y 280 CV, transmisión automática y tracción total. Subcategorías: 0601 vehículos de ruedas, 0201 telecomunicaciones "
        "y mando y control, 0102 armamento secundario.",
    ),
    (
        "VTL 4X4 TRAMONTANA PUESTO DE MANDO",
        "232033X900002",
        "TRM-4X4-PC",
        "DEMO1",
        "Variante puesto de mando del VTL 4X4 Tramontana, con ordenador de misión y radios de mando adicionales. Tiene "
        "CONFUNFIS propia. Subcategorías: 0601, 0201 y 0102.",
    ),
    (
        "RADIO VHF RT-500",
        "582033X901001",
        "RT-500-V2",
        "DEMO3",
        "Radioteléfono VHF vehicular de voz y datos. CUF montado en la posición E12300 del VTL 4X4 Tramontana. "
        "Subcategoría: 0201.",
    ),
    (
        "MOTOR DIESEL 6 CIL DM-6 280 CV",
        "281533X900101",
        "DM6-280-00",
        "DEMO2",
        "Motor diésel de 6 cilindros y 280 CV del VTL 4X4 Tramontana, gestionado como material reparable independiente, "
        "con control de vida por horas. Subcategoría: 0601.",
    ),
    (
        "VTO GREGAL",
        "235033X900003",
        "GRG-VTO-A",
        "DEMO1",
        "Vehículo de transporte sobre orugas. Comparte el grupo motor DM-6 con el Tramontana y monta cadenas. "
        "Subcategoría: 0602 vehículos de cadenas.",
    ),
)
DEMO_ROLES = (
    ("analista.dev@aal-dev.es", "analista"),
    ("revisor.dev@aal-dev.es", "revisor"),
    ("observador.dev@aal-dev.es", "observador"),
)


async def seed() -> None:
    async with async_session_factory() as db:
        users = {}
        for email, _role in DEMO_ROLES:
            user = (await db.execute(select(User).where(User.email == email, User.deleted_at.is_(None)))).scalar_one_or_none()
            if user is None:
                print(f"No existe {email} (scripts/seed_dev_data.py): no se le asigna rol.", file=sys.stderr)
            else:
                users[email] = user
        for name, noc, part_number, ncage, description in DEMO_MATERIALS:
            material = (await db.execute(select(Material).where(Material.name == name, Material.deleted_at.is_(None)))).scalar_one_or_none()
            if material is None:
                material = Material(name=name, noc=noc, part_number=part_number, ncage=ncage, description=description, version=1)
                db.add(material)
                await db.flush()
                audit.record(
                    db, action="material.created", entity_type="material", entity_id=str(material.id), material_id=material.id,
                    after={"name": name, "noc": noc, "part_number": part_number, "ncage": ncage},
                )
                print(f"Material creado: {name}")
            else:
                print(f"Ya existe: {name} (no se modifica)")
            for email, role in DEMO_ROLES:
                user = users.get(email)
                if user is None or await db.get(UserMaterialRole, (user.id, material.id)) is not None:
                    continue
                db.add(UserMaterialRole(user_id=user.id, material_id=material.id, role_code=role))
                audit.record(
                    db, action="material_role.assigned", entity_type="user_material_role", entity_id=f"{user.id}:{material.id}",
                    material_id=material.id, after={"user": email, "role": role},
                )
                print(f"  {email}: {role} en {name}")
        await db.commit()
    await engine.dispose()


def main() -> int:
    if get_settings().environment == "production":
        print("seed_demo_materials no se ejecuta con ENVIRONMENT=production.", file=sys.stderr)
        return 1
    asyncio.run(seed())
    return 0


if __name__ == "__main__":
    utf8_output()
    sys.exit(cancellable(main))
