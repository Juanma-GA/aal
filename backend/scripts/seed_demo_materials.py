"""The demo materials (E10, D14): the five materials of
demo/LEEME_DATOS_DEMO.md §1 (VTL 4X4 TRAMONTANA and its relatives, all
invented), with the three development users assigned (analista, revisor,
observador). Never on a server (refused with ENVIRONMENT=production).

    python scripts/seed_demo_materials.py        (from backend/)

E11: when a catalog version is active (demo/CONF_FUN_DEMO.xlsx imported),
each material gets its subcategories (Tramontana and its Puesto de mando
0601+0201+0102, Radio 0201, Motor 0601, Gregal 0602) and the Puesto de mando
is a copy of the Tramontana (copied_from). Without a catalog it says so and
assigns no subcategory.

Idempotent: a material whose name already exists is not duplicated nor
changed (but for what is missing: its catalog version, its subcategories
when it has none, the Puesto de mando's copied_from), and a role already
assigned is kept. The development users come from scripts/seed_dev_data.py;
one that does not exist is reported and skipped.
"""

import asyncio
import sys

from _common import cancellable, utf8_output

from sqlalchemy import select

from app.core.config import get_settings
from app.db.base import async_session_factory, engine
from app.models import CatalogVersion, Material, User, UserMaterialRole
from app.services import audit, cuf

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
# demo/LEEME_DATOS_DEMO.md §1: the subcategories of each material.
DEMO_SUBCATEGORIES = {
    "VTL 4X4 TRAMONTANA": ("0601", "0201", "0102"),
    "VTL 4X4 TRAMONTANA PUESTO DE MANDO": ("0601", "0201", "0102"),
    "RADIO VHF RT-500": ("0201",),
    "MOTOR DIESEL 6 CIL DM-6 280 CV": ("0601",),
    "VTO GREGAL": ("0602",),
}
# The variant made "a partir de otro": copy -> original.
DEMO_COPIES = {"VTL 4X4 TRAMONTANA PUESTO DE MANDO": "VTL 4X4 TRAMONTANA"}
DEMO_ROLES = (
    ("analista.dev@aal-dev.es", "analista"),
    ("revisor.dev@aal-dev.es", "revisor"),
    ("observador.dev@aal-dev.es", "observador"),
)


async def seed() -> None:
    async with async_session_factory() as db:
        catalog = (await db.execute(select(CatalogVersion).where(CatalogVersion.is_active))).scalar_one_or_none()
        if catalog is None:
            print("No hay catálogo importado (demo/CONF_FUN_DEMO.xlsx): no se asignan subcategorías.", file=sys.stderr)
        users = {}
        for email, _role in DEMO_ROLES:
            user = (await db.execute(select(User).where(User.email == email, User.deleted_at.is_(None)))).scalar_one_or_none()
            if user is None:
                print(f"No existe {email} (scripts/seed_dev_data.py): no se le asigna rol.", file=sys.stderr)
            else:
                users[email] = user
        materials: dict[str, Material] = {}
        for name, noc, part_number, ncage, description in DEMO_MATERIALS:
            material = (await db.execute(select(Material).where(Material.name == name, Material.deleted_at.is_(None)))).scalar_one_or_none()
            source = materials.get(DEMO_COPIES.get(name, ""))
            if material is None:
                material = Material(
                    name=name, noc=noc, part_number=part_number, ncage=ncage, description=description, version=1,
                    catalog_version_id=source.catalog_version_id if source else (catalog.id if catalog else None),
                    copied_from_material_id=source.id if source else None,
                )
                db.add(material)
                await db.flush()
                if source is not None:
                    await cuf.set_subcategories(db, material, set(await cuf.subcategory_codes(db, source.id)))
                audit.record(
                    db, action="material.copied" if source else "material.created", entity_type="material", entity_id=str(material.id),
                    material_id=material.id, after={"name": name, "noc": noc, "part_number": part_number, "ncage": ncage, "from": source.name if source else None},
                )
                print(f"Material creado: {name}{f' (copia de {source.name})' if source else ''}")
            else:
                print(f"Ya existe: {name}")
                if source is not None and material.copied_from_material_id is None:
                    material.copied_from_material_id = source.id
                    material.version += 1
                    audit.record(db, action="material.updated", entity_type="material", entity_id=str(material.id), material_id=material.id, after={"copied_from": source.name})
                    print(f"  ahora es variante de {source.name}")
                if material.catalog_version_id is None and catalog is not None:
                    material.catalog_version_id = catalog.id
                    material.version += 1
                    audit.record(
                        db, action="material.catalog_version_changed", entity_type="material", entity_id=str(material.id),
                        material_id=material.id, before={"catalog_version_id": None}, after={"catalog_version_id": str(catalog.id)},
                    )
            materials[name] = material
            available: list[str] = []
            if catalog is not None and material.catalog_version_id == catalog.id and not await cuf.subcategory_codes(db, material.id):
                available = list(await cuf.sns_by_subcategory(db, catalog.id, list(DEMO_SUBCATEGORIES[name])))
                missing = [c for c in DEMO_SUBCATEGORIES[name] if c not in available]
                if missing:
                    print(f"  el catálogo activo no tiene las subcategorías {', '.join(missing)}", file=sys.stderr)
            if catalog is not None and available:
                await cuf.set_subcategories(db, material, set(available))
                material.version += 1
                audit.record(
                    db, action="material.subcategories_changed", entity_type="material", entity_id=str(material.id), material_id=material.id,
                    before={"subcategories": []}, after={"subcategories": sorted(available)},
                )
                print(f"  subcategorías: {', '.join(sorted(available))}")
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
