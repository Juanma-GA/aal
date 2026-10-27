"""Recomputes the findings kept on the CONFUNFIS records (E16): rows,
incompatibilities, functional products and the parts of every article,
with the validator's rules (app/validacion/), after a change of the rules'
code (the records stored by E13-E15 carry the old OF-*, OP-*, OPF-*, OI-*):

    python scripts/refresh_findings.py        (from backend/)

`npm run update` runs it when the migrations or the rules change. Only the
findings are written: no version nor date moves, nothing is audited (they
are calculated, like the tree's totals).
"""

import asyncio
import sys

from _common import utf8_output
from sqlalchemy import select

from app.db.base import async_session_factory, engine
from app.models import Material
from app.services import confunfis
from app.services import confunfis_extras as extras


async def main() -> int:
    async with async_session_factory() as session:
        materials = list((await session.execute(select(Material).where(Material.deleted_at.is_(None)).order_by(Material.name))).scalars())
        for material in materials:
            await confunfis.refresh_observations(session, material)
            await extras.refresh_products(session, material)
        await extras.refresh_parts(session, None)
        await session.commit()
    await engine.dispose()
    print(f"Hallazgos recalculados en {len(materials)} materiales y en las tablas de partes.")
    return 0


if __name__ == "__main__":
    utf8_output()
    sys.exit(asyncio.run(main()))
