"""The demo CONFUNFIS (E13, D14): loads the sheet CON_FUN_FIS of
demo/CONFUNFIS_DEMO_TRAMONTANA.xlsx (46 invented rows) into VTL 4X4
TRAMONTANA with the same service as the screen (app/services/confunfis.py:
the link with the articles included) but lenient: the anomalies the demo
carries on purpose for E16 are kept and observed, not refused. Then, if the
CONFUNFIS of VTL 4X4 TRAMONTANA PUESTO DE MANDO is empty, it is created by
copying the Tramontana's (as "Crear a partir de otro" does). Never on a
server (refused with ENVIRONMENT=production).

E14: also the sheets TABLA PRODUCTOS FUNCIONALES (8 functional products of
the Tramontana) and TABLA DE PARTES (the breakdown of the water pump DM-6),
and the demo's extra function (the radio E12300 is also E19200) and
incompatibility (L41120 requires L41130); the Puesto de mando gets them on
its own rows (copied with the CONFUNFIS, or added to one copied before).

    python scripts/seed_demo_confunfis.py           (from backend/)
    python scripts/seed_demo_confunfis.py --reset   (the demo as it came)

E17: --reset leaves the demo clean after a rehearsal of the hito de demo 2
(docs/encargos/E17.md §6): it removes, for good, the CONFUNFIS of the
Tramontana and of the Puesto de mando with their baselines, authorizations,
validations and accepted findings, puts the demo articles back as
demo/FICHERO_CARGA_DEMO.xlsx has them (seed_demo_articles.py, plus the P/N
that demo_corregir_hallazgos.py gives the filler cap), and loads it all
again. A baseline only goes this way: never through the API.

Run it after seed_demo_materials.py and seed_demo_articles.py (and the
catalog demo/CONF_FUN_DEMO.xlsx imported): it says what is missing.
Idempotent: a material whose CONFUNFIS has rows is left as it is, and so is
each E14 table that already has something.
"""

import argparse
import asyncio
import sys
from pathlib import Path

from _common import cancellable, utf8_output
from sqlalchemy import delete, func, select

from app.core.config import get_settings
from app.db.base import async_session_factory, engine
from app.models import (
    Article,
    ArticleReference,
    Baseline,
    ChangeAuthorization,
    ExtraFunction,
    FindingAcceptance,
    FunctionalProduct,
    Incompatibility,
    Material,
    PhysicalPosition,
    ValidationRun,
)
from app.services import audit, changes, confunfis, cuf
from app.services import confunfis_extras as extras
from app.services.confunfis_sheet import read_parts, read_products, read_sheet, split, split_part
from app.services.import_jobs import limits

DEMO = Path(__file__).resolve().parents[2] / "demo" / "CONFUNFIS_DEMO_TRAMONTANA.xlsx"
TRAMONTANA = "VTL 4X4 TRAMONTANA"
PUESTO_DE_MANDO = "VTL 4X4 TRAMONTANA PUESTO DE MANDO"
# The demo's examples of §9.1.1 and of the incompatibilities (E14 §2.3).
EXTRA_FUNCTION = ("E12300", "E19200", "funcion_principal", "conmutador de datos integrado")
INCOMPATIBILITY = ("L41120", "requiere", "L41130", "compatibilidad SW/FW")


async def _material(db, name: str) -> Material | None:
    return (await db.execute(select(Material).where(Material.name == name, Material.deleted_at.is_(None)))).scalar_one_or_none()


async def _rows(db, material: Material) -> int:
    query = select(func.count()).select_from(PhysicalPosition).where(PhysicalPosition.material_id == material.id, PhysicalPosition.deleted_at.is_(None))
    return await db.scalar(query) or 0


def _problems(read) -> list:
    return read.errors + [i for r in read.rows for i in r.errors]


async def _products(db, tramontana: Material, data: bytes) -> int:
    if await extras.live_products(db, tramontana.id):
        print(f"{TRAMONTANA} ya tiene productos funcionales: no se tocan.")
        return 0
    read = await asyncio.to_thread(read_products, data, await limits(db))
    if _problems(read):
        for issue in _problems(read):
            print(f"  - {issue.as_json()}", file=sys.stderr)
        print("La hoja TABLA PRODUCTOS FUNCIONALES de demo no se puede leer.", file=sys.stderr)
        return 1
    for parsed in read.rows:
        await extras.save_product(db, tramontana, parsed.values, None, source="seed")
    await extras.refresh_products(db, tramontana)
    print(f"{TRAMONTANA}: {len(read.rows)} productos funcionales cargados.")
    return 0


async def _parts(db, data: bytes) -> int:
    read = await asyncio.to_thread(read_parts, data, await limits(db))
    if _problems(read):
        for issue in _problems(read):
            print(f"  - {issue.as_json()}", file=sys.stderr)
        print("La hoja TABLA DE PARTES de demo no se puede leer.", file=sys.stderr)
        return 1
    loaded: dict = {}
    skipped: set[str] = set()
    for parsed in read.rows:
        parent_id, values, identity = split_part(parsed.values)
        parent = (await db.execute(select(Article).where(Article.noc == parent_id["noc"], Article.deleted_at.is_(None)))).scalar_one_or_none()
        if parent is None:
            print(f"No existe el artículo {parent_id['noc']} (scripts/seed_demo_articles.py): sus partes no se cargan.", file=sys.stderr)
            continue
        if parent.id not in loaded and await extras.live_parts(db, parent.id):
            skipped.add(parent.nombre)
            continue
        await extras.save_part(db, parent, values, None, source="seed", strict=False, identity=identity)
        loaded[parent.id] = loaded.get(parent.id, 0) + 1
    await extras.refresh_parts(db)
    for name in sorted(skipped):
        print(f"{name} ya tiene tabla de partes: no se toca.")
    if loaded:
        print(f"Tabla de partes: {sum(loaded.values())} partes cargadas.")
    return 0


def _first(rows: list[PhysicalPosition], sns: str) -> PhysicalPosition | None:
    return next((r for r in rows if r.sns == sns), None)


async def _examples(db, tramontana: Material) -> None:
    rows = await confunfis.live_rows(db, tramontana.id)
    if not await extras.live_extras(db, tramontana.id):
        sns, extra, criterion, comment = EXTRA_FUNCTION
        row = _first(rows, sns)
        problems = await extras.check_extra(db, tramontana, row, extra, criterion) if row else ["no row"]
        if problems:
            print(f"No se añade la función adicional de demo ({sns} → {extra}): {problems}", file=sys.stderr)
        else:
            await extras.add_extra(db, tramontana, row, extra, criterion, comment, None, source="seed")
            print(f"{TRAMONTANA}: función adicional {sns} → {extra}.")
    if not await extras.live_incompatibilities(db, tramontana.id):
        sns_a, kind, sns_b, reason = INCOMPATIBILITY
        a, b = _first(rows, sns_a), _first(rows, sns_b)
        if a is None or b is None:
            print(f"No se añade la incompatibilidad de demo ({sns_a} {kind} {sns_b}): falta una fila.", file=sys.stderr)
        else:
            await extras.add_incompatibility(db, tramontana, a, b, kind, reason, None, source="seed")
            print(f"{TRAMONTANA}: {sns_a} {kind} {sns_b}.")


def _position(r: PhysicalPosition) -> tuple:
    return (r.sns, r.co, r.al, r.cs_sns, r.cs_co, r.cs_al)


async def _extras_to_variant(db, tramontana: Material, variant: Material) -> None:
    """A Puesto de mando copied before E14: its rows, matched by position and CS."""
    if await extras.live_products(db, variant.id) or await extras.live_extras(db, variant.id) or await extras.live_incompatibilities(db, variant.id):
        print(f"{PUESTO_DE_MANDO} ya tiene productos, funciones adicionales o incompatibilidades: no se tocan.")
        return
    theirs: dict[tuple, object] = {}
    for r in await confunfis.live_rows(db, variant.id):
        theirs.setdefault(_position(r), r.id)
    mapping = {r.id: theirs[_position(r)] for r in await confunfis.live_rows(db, tramontana.id) if _position(r) in theirs}
    counts = await extras.copy_extras(db, tramontana, variant, mapping, None)
    await confunfis.refresh_observations(db, variant)
    print(f"{PUESTO_DE_MANDO}: {counts['products']} productos, {counts['extra_functions']} funciones adicionales y "
          f"{counts['incompatibilities']} incompatibilidades copiados de {TRAMONTANA}.")


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

        data = DEMO.read_bytes()
        existing = await _rows(db, tramontana)
        if existing:
            print(f"{TRAMONTANA} ya tiene CONFUNFIS ({existing} filas): no se toca.")
        else:
            read = await asyncio.to_thread(read_sheet, data, await limits(db))
            problems = _problems(read)
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

        if await _products(db, tramontana, data) or await _parts(db, data):
            return 1
        await _examples(db, tramontana)
        await confunfis.refresh_observations(db, tramontana)
        await db.commit()

        variant = await _material(db, PUESTO_DE_MANDO)
        if variant is None:
            print(f"No existe {PUESTO_DE_MANDO}: no se copia.", file=sys.stderr)
        elif await _rows(db, variant):
            print(f"{PUESTO_DE_MANDO} ya tiene CONFUNFIS: no se toca.")
            await _extras_to_variant(db, tramontana, variant)
            await db.commit()
        else:
            copied = await confunfis.copy_confunfis(db, tramontana, variant, cuf.CopyOptions(copy_members=False))
            await db.commit()
            print(f"{PUESTO_DE_MANDO}: {copied} filas copiadas de {TRAMONTANA}.")
    return 0


async def reset() -> int:
    """Everything a rehearsal leaves on the two demo CUF, removed for good (unguarded: a baseline
    in review or reviewed would refuse it); then the demo articles back as the file has them."""
    import demo_corregir_hallazgos
    import seed_demo_articles

    async with async_session_factory() as db:
        materials = [m for m in (await _material(db, TRAMONTANA), await _material(db, PUESTO_DE_MANDO)) if m is not None]
        ids = [m.id for m in materials]
        with changes.unguarded():
            # In this order: a baseline holds its validation; the extras hang from the rows.
            for model in (Baseline, ChangeAuthorization, FindingAcceptance, ValidationRun, Incompatibility, ExtraFunction, FunctionalProduct, PhysicalPosition):
                await db.execute(delete(model).where(model.material_id.in_(ids)))
            await db.execute(delete(ArticleReference).where(
                ArticleReference.pn == demo_corregir_hallazgos.CAP_PN, ArticleReference.ncage == demo_corregir_hallazgos.CAP_NCAGE,
            ))
            for m in materials:
                audit.record(db, action="confunfis.reset", entity_type="material", entity_id=str(m.id), material_id=m.id,
                             after={"script": "seed_demo_confunfis --reset"})
            await db.commit()
        print(f"Borrado: CONFUNFIS, baselines, autorizaciones y validaciones de {', '.join(m.name for m in materials) or 'nada'}.")
    return await seed_demo_articles.seed()


async def run(reset_first: bool = False) -> int:
    try:
        if reset_first and await reset():
            return 1
        return await seed()
    finally:
        await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--reset", action="store_true", help="borra la CONFUNFIS de demo, sus baselines y autorizaciones y la vuelve a cargar")
    args = parser.parse_args()
    if get_settings().environment == "production":
        print("seed_demo_confunfis no se ejecuta con ENVIRONMENT=production.", file=sys.stderr)
        return 1
    return asyncio.run(run(args.reset))


if __name__ == "__main__":
    utf8_output()
    sys.exit(cancellable(main))
