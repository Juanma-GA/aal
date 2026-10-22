"""Reloads the reference tables and the article fields from
app/seeds/reference_tables_seed.yaml (E03), after the seed changes:

    python scripts/load_reference_tables.py        (from backend/)

Adds the new tables and values; a value already in the database is never
modified (an admin may have edited it): where it differs from the seed it
is listed, so a person decides. The tables' name, source, note and
attribute schema, and the 30 article fields, follow the seed (they are not
editable in the app). Checks the seed first (unique codes, codes as text,
attributes, reference tables of the fields) and loads nothing if it fails.
The run is recorded in the audit log.
"""

import asyncio
import sys

from _common import utf8_output

from app.db.base import async_session_factory, engine
from app.services import audit
from app.services.reference_seed import SeedError, load_reference_tables


async def main() -> int:
    async with async_session_factory() as session:
        try:
            report = await (await session.connection()).run_sync(load_reference_tables)
        except SeedError as exc:
            print("La semilla no pasa la validación; no se ha cargado nada:", file=sys.stderr)
            for problem in exc.problems:
                print(f"  - {problem}", file=sys.stderr)
            return 1
        audit.record(
            session,
            action="reference_tables.loaded",
            entity_type="reference_table",
            entity_id="seed",
            after={
                "tables_added": report.tables_added,
                "values_added": report.values_added,
                "fields_added": report.fields_added,
                "fields_updated": report.fields_updated,
                "differences": len(report.differences),
                "values_not_in_seed": report.values_not_in_seed,
            },
        )
        await session.commit()
    await engine.dispose()
    print(
        f"Tablas nuevas: {report.tables_added}. Valores nuevos: {report.values_added}. "
        f"Campos del artículo nuevos: {report.fields_added}; actualizados: {report.fields_updated}."
    )
    if report.differences:
        print("Valores que difieren de la semilla (se conservan los de la base):")
        for d in report.differences:
            print(f"  - {d.table}/{d.code} {d.field}: base {d.stored!r}, semilla {d.seed!r}")
    if report.values_not_in_seed:
        print(f"En la base pero no en la semilla (se conservan): {', '.join(report.values_not_in_seed)}")
    return 0


if __name__ == "__main__":
    utf8_output()
    sys.exit(asyncio.run(main()))
