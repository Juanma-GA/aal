"""Reloads the PALI module catalog from app/seeds/module_catalog_seed.yaml
(E02), after the seed changes:

    python scripts/load_module_catalog.py        (from backend/)

Adds the new groups and modules and updates the texts of the existing ones;
the status and route an admin set are never overwritten. Checks the seed
first (codes, groups, dependencies without cycles, RF-01..RF-41) and loads
nothing if it fails. The run is recorded in the audit log.
"""

import asyncio
import sys

from _common import utf8_output

from app.db.base import async_session_factory, engine
from app.services import audit
from app.services.module_catalog import SeedError, load_catalog


async def main() -> int:
    async with async_session_factory() as session:
        try:
            report = await (await session.connection()).run_sync(load_catalog)
        except SeedError as exc:
            print("La semilla no pasa la validación; no se ha cargado nada:", file=sys.stderr)
            for problem in exc.problems:
                print(f"  - {problem}", file=sys.stderr)
            return 1
        audit.record(
            session,
            action="module_catalog.loaded",
            entity_type="module_catalog",
            entity_id="seed",
            after={
                "groups_added": report.groups_added,
                "modules_added": report.modules_added,
                "modules_updated": report.modules_updated,
                "modules_not_in_seed": report.modules_not_in_seed,
            },
        )
        await session.commit()
    await engine.dispose()
    print(f"Grupos nuevos: {report.groups_added}. Módulos nuevos: {report.modules_added}; con textos actualizados: {report.modules_updated}.")
    if report.modules_not_in_seed:
        print(f"En la base pero ya no en la semilla (se conservan): {', '.join(report.modules_not_in_seed)}")
    return 0


if __name__ == "__main__":
    utf8_output()
    sys.exit(asyncio.run(main()))
