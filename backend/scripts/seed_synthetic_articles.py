"""Synthetic articles for a performance check (E13): N articles with every
S/N, code and numeric field filled, invented NPC (NNNN33X9NNNNN) and names
"[perf] …". Never on a server (refused with ENVIRONMENT=production).

    python scripts/seed_synthetic_articles.py 2000      (from backend/)

They are inserted in bulk, without audit rows: they are test data that the
check removes again (purge_verify_data.py --restore-articles).
"""

import asyncio
import sys
import uuid

from _common import utf8_output

from sqlalchemy import insert

from app.core.config import get_settings
from app.db.base import async_session_factory, engine
from app.models import Article

PREFIX = "[perf] "


def row(i: int) -> dict:
    yes = "S" if i % 2 else "N"
    return {
        "id": uuid.uuid4(), "noc": f"{i % 10000:04d}33X9{i:05d}", "nombre": f"{PREFIX}ARTÍCULO {i:05d}", "origen_nombre": "coloquial",
        "grupo_estructural": "4", "codigo_seguridad": "U", "reparable": "N", "consumible": yes, "unidad_suministro": "EA",
        "control_unitario": "N", "precio_estandar": i % 5000, "documentacion_adjunta": "N", "peso": 1, "unidad_peso": "KG",
        "control_vida": "N", "escalon_1": "N", "escalon_2": "N", "escalon_3": "N", "escalon_4": "N", "control_configuracion": "N",
        "mantenimiento_preventivo": "N", "version": 1,
    }


async def main(count: int) -> int:
    async with async_session_factory() as db:
        await db.execute(insert(Article), [row(i) for i in range(1, count + 1)])
        await db.commit()
    await engine.dispose()
    print(f"Artículos sintéticos: {count}")
    return 0


if __name__ == "__main__":
    utf8_output()
    if get_settings().environment == "production":
        print("No se ejecuta con ENVIRONMENT=production.", file=sys.stderr)
        sys.exit(1)
    sys.exit(asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 2000)))
