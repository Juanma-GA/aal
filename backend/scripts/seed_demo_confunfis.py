"""The demo CONFUNFIS (E13, D14): loads the sheet CON_FUN_FIS of
demo/CONFUNFIS_DEMO_TRAMONTANA.xlsx (46 invented rows) into VTL 4X4
TRAMONTANA with the same service as the screen (app/services/confunfis.py:
the link with the articles included) but lenient: the anomalies the demo
carries on purpose for E16 are kept and observed, not refused. Then, if the
CONFUNFIS of VTL 4X4 TRAMONTANA PUESTO DE MANDO is empty, it is created by
copying the Tramontana's (as "Crear a partir de otro" does). Never on a
server (refused with ENVIRONMENT=production).

    python scripts/seed_demo_confunfis.py        (from backend/)

Run it after seed_demo_materials.py and seed_demo_articles.py (and the
catalog demo/CONF_FUN_DEMO.xlsx imported): it says what is missing.
Idempotent: a material whose CONFUNFIS has rows is left as it is.
"""

import asyncio
import sys
from pathlib import Path

from _common import cancellable, utf8_output
from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.base import async_session_factory, engine
from app.models import Article, Material, PhysicalPosition
from app.services import audit, confunfis, cuf
from app.services.confunfis_sheet import read_sheet, split
from app.services.import_jobs import limits

DEMO = Path(__file__).resolve().parents[2] / "demo" / "CONFUNFIS_DEMO_TRAMONTANA.xlsx"
TRAMONTANA = "VTL 4X4 TRAMONTANA"
PUESTO_DE_MANDO = "VTL 4X4 TRAMONTANA PUESTO DE MANDO"


async def _material(db, name: str) -> Material | None:
    return (await db.execute(select(Material).where(Material.name == name, Material.deleted_at.is_(None)))).scalar_one_or_none()


async def _rows(db, material: Material) -> int:
    query = select(func.count()).select_from(PhysicalPosition).where(PhysicalPosition.material_id == material.id, PhysicalPosition.deleted_at.is_(None))
    return await db.scalar(query) or 0


async def seed() -> int:
    async with async_session_factory() as db:
        tramontana = await _material(db, TRAMONTANA)
        if tramontana is None:
            print(f"No existe el material {TRAMONTANA}: ejecuta antes scripts/seed_demo_materials.py.", file=sys.stderr)
            return 1
        if not await cuf.normalized_config(db, tramontana):
            print(f"{TRAMONTANA} no tiene configuración normalizada (importa demo/CONF_FUN_DEMO.xlsx y ejecuta seed_demo_materials.py): "
                  "todas sus filas saldrán fuera de la configuración.", file=sys.stderr)
        if not await db.scalar(select(func.count()).select_from(Article).where(Article.deleted_at.is_(None), Article.origin == "maestro")):
            print("No hay artículos de demo (scripts/seed_demo_articles.py): se crearán como provisionales.", file=sys.stderr)

        existing = await _rows(db, tramontana)
        if existing:
            print(f"{TRAMONTANA} ya tiene CONFUNFIS ({existing} filas): no se toca.")
        else:
            read = await asyncio.to_thread(read_sheet, DEMO.read_bytes(), await limits(db))
            problems = read.errors + [i for r in read.rows for i in r.errors]
            if problems:
                for issue in problems:
                    print(f"  - {issue.as_json()}", file=sys.stderr)
                print("La hoja CON_FUN_FIS de demo no se puede leer.", file=sys.stderr)
                return 1
            config = set(await cuf.normalized_config(db, tramontana))
            for parsed in read.rows:
                values, identity = split(parsed.values)
                await confunfis.save_row(db, tramontana, values, None, source="seed", strict=False, identity=identity, config=config)
            await confunfis.refresh_observations(db, tramontana)
            audit.record(
                db, action="confunfis.seeded", entity_type="material", entity_id=str(tramontana.id), material_id=tramontana.id,
                after={"file_name": DEMO.name, "rows": len(read.rows)},
            )
            await db.commit()
            print(f"{TRAMONTANA}: {len(read.rows)} filas cargadas.")

        variant = await _material(db, PUESTO_DE_MANDO)
        if variant is None:
            print(f"No existe {PUESTO_DE_MANDO}: no se copia.", file=sys.stderr)
        elif await _rows(db, variant):
            print(f"{PUESTO_DE_MANDO} ya tiene CONFUNFIS: no se toca.")
        else:
            copied = await confunfis.copy_confunfis(db, tramontana, variant, cuf.CopyOptions(copy_members=False))
            await db.commit()
            print(f"{PUESTO_DE_MANDO}: {copied} filas copiadas de {TRAMONTANA}.")
    return 0


async def run() -> int:
    try:
        return await seed()
    finally:
        await engine.dispose()


def main() -> int:
    if get_settings().environment == "production":
        print("seed_demo_confunfis no se ejecuta con ENVIRONMENT=production.", file=sys.stderr)
        return 1
    return asyncio.run(run())


if __name__ == "__main__":
    utf8_output()
    sys.exit(cancellable(main))
