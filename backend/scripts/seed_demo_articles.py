"""The demo articles (E12, D14): imports demo/FICHERO_CARGA_DEMO.xlsx (45
invented articles with their 30 MAR06 fields) with the same service as
Artículos -> Importar (app/services/article_import.py): the same analysis,
the same AR findings, the same audit. Never on a server (refused with
ENVIRONMENT=production).

    python scripts/seed_demo_articles.py        (from backend/)

Idempotent: a second run finds the 45 unchanged and writes nothing. An
article someone edited since is set back to the file's data (as a second
import of the file would).
"""

import asyncio
import sys
from pathlib import Path

from _common import cancellable, utf8_output

from app.core.config import get_settings
from app.db.base import async_session_factory, engine
from app.io_excel.reader import read_rows
from app.io_excel.targets import get_target
from app.services import audit
from app.services.article_import import FICHERO_CARGA
from app.services.import_jobs import limits

DEMO = Path(__file__).resolve().parents[2] / "demo" / "FICHERO_CARGA_DEMO.xlsx"


async def seed() -> int:
    target = get_target(FICHERO_CARGA)
    async with async_session_factory() as db:
        template = await target.template(db, {})
        read = await asyncio.to_thread(read_rows, template, DEMO.read_bytes(), await limits(db))
        report = await target.analyze(db, {}, template, read)
        counts = report["counts"]
        if counts["errors"]:
            for issue in report["errors"]:
                print(f"  - {issue['code']} {issue['params']}", file=sys.stderr)
            print("El fichero de demo no se puede importar.", file=sys.stderr)
            return 1
        print(f"Filas: {counts['rows']}. Nuevos: {counts['new']}; modificados: {counts['modified']}; sin cambios: {counts['unchanged']}; rechazados: {counts['rejected']}.")
        for code in sorted(report["ar"]):
            if report["ar"][code]:
                print(f"  {code}: {', '.join(sorted({i['name'] for i in report['ar'][code]}))}")
        if counts["new"] or counts["modified"]:
            await target.apply_report(db, report, template, None, {"file_name": DEMO.name, "script": "seed_demo_articles"}, None)
            audit.record(db, action="articles.seeded", entity_type="article", entity_id="seed", after={"file_name": DEMO.name, "counts": counts})
            await db.commit()
    return 0


async def run() -> int:
    try:
        return await seed()
    finally:
        await engine.dispose()


def main() -> int:
    if get_settings().environment == "production":
        print("seed_demo_articles no se ejecuta con ENVIRONMENT=production.", file=sys.stderr)
        return 1
    return asyncio.run(run())


if __name__ == "__main__":
    utf8_output()
    sys.exit(cancellable(main))
