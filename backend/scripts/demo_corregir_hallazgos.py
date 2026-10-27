"""Corrects the 10 blocking findings of the demo in VTL 4X4 TRAMONTANA (E17),
as the development analyst and audited, so the hito de demo 2 starts from
a CUF that validates green:

    python scripts/demo_corregir_hallazgos.py                 (from backend/)
    python scripts/demo_corregir_hallazgos.py --dejar CF-007  (one left, to fix live)

  CF-001  removes the row B35010 (tyre chains on a wheeled vehicle)
  CF-002  the shock absorber's CS -> 000000 01 00 (the CUF: there is no B30000 row)
  CF-007  the air filter's CS -> A20000 01 00 (the engine)
  CF-012  gives the filler cap a P/N + NCAGE
  CF-014  gives the main wiring harness its function
  CF-015  removes the second (duplicate) brake disc
  PF-001  the supply unit ZZ -> DR
  AR-002  the expansion tank gets a maintenance echelon
  AR-003  the viscous coupling gets its weight unit
  AR-006  the con rod gets its life control

Idempotent: what is already corrected is left as it is. Refuses with
ENVIRONMENT=production. The analyst is analista.dev@aal-dev.es
(scripts/seed_dev_data.py) or DEMO_ANALYST_EMAIL; no password is needed.
Run it before any baseline of the Tramontana (the CONFUNFIS of a reviewed
baseline only changes with an authorization).
"""

import argparse
import asyncio
import os
import sys
from decimal import Decimal

from _common import cancellable, utf8_output
from sqlalchemy import select

from app.core.config import get_settings
from app.db.base import async_session_factory, engine
from app.models import Article, Material, PhysicalPosition, User
from app.services import audit, changes, confunfis
from app.services import confunfis_extras as extras
from app.services.articles import Checker, autocorrect, data_of, life_of, set_data, set_life, snapshot
from app.services.reference import codes_by_state
from app.validacion.articulos import LEVELS, LifeControl

TRAMONTANA = "VTL 4X4 TRAMONTANA"
CODES = ("CF-001", "CF-002", "CF-007", "CF-012", "CF-014", "CF-015", "PF-001", "AR-002", "AR-003", "AR-006")
CAP_PN, CAP_NCAGE = "TAP-22140-02", "DEMO1"
HARNESS_FUNCTION = "Distribuir la energía eléctrica a los equipos del vehículo"


def _row(rows: list[PhysicalPosition], sns: str, co: str = "01", al: str = "00") -> list[PhysicalPosition]:
    return sorted((r for r in rows if (r.sns, r.co, r.al) == (sns, co, al)), key=lambda r: (r.created_at, str(r.id)))


async def _save_cs(db, material, row: PhysicalPosition, cs: tuple[str, str, str], user: User) -> bool:
    if (row.cs_sns, row.cs_co, row.cs_al) == cs:
        return False
    values = {**{n: getattr(row, n) for n in confunfis.FIELDS}, "cs_sns": cs[0], "cs_co": cs[1], "cs_al": cs[2]}
    await confunfis.save_row(db, material, values, user.id, source=row.source, strict=False, row=row)
    return True


async def _edit_article(db, article: Article, fields: dict, user: User, life: list[LifeControl] | None = None) -> bool:
    data = data_of(article)
    if all(data.get(k) == v for k, v in fields.items()) and (life is None or life_of(article)):
        return False
    before = snapshot(article)
    data = {**data, **fields}
    corrections = autocorrect(data)
    set_data(article, data)
    if life is not None:
        set_life(article, life)
    (await Checker.load(db)).recheck(article)
    article.version += 1
    article.updated_by = user.id
    audit.record(db, action="article.updated", entity_type="article", entity_id=str(article.id), user_id=user.id,
                 before=before, after={**snapshot(article), "corrections": corrections, "script": "demo_corregir_hallazgos"})
    return True


async def run(leave: set[str]) -> int:
    email = os.environ.get("DEMO_ANALYST_EMAIL", "analista.dev@aal-dev.es")
    async with async_session_factory() as db:
        material = (await db.execute(select(Material).where(Material.name == TRAMONTANA, Material.deleted_at.is_(None)))).scalar_one_or_none()
        user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if material is None or user is None:
            print(f"Falta {'el material ' + TRAMONTANA if material is None else 'el usuario ' + email}: lanza antes las semillas.", file=sys.stderr)
            return 1
        done: list[str] = []
        with changes.acting(user.id):
            rows = await confunfis.live_rows(db, material.id)
            articles = {a.id: a for a in (await db.execute(select(Article).where(Article.id.in_({r.article_id for r in rows if r.article_id})))).scalars()}

            def article_named(name: str) -> Article | None:
                return next((a for a in articles.values() if (a.nombre or "").upper() == name), None)

            if "CF-001" not in leave:
                for r in _row(rows, "B35010"):
                    await confunfis.delete_row(db, material, r, user.id)
                    done.append("CF-001")
            if "CF-002" not in leave:
                for r in _row(rows, "B31010"):
                    if await _save_cs(db, material, r, ("000000", "01", "00"), user):
                        done.append("CF-002")
            if "CF-007" not in leave:
                for r in _row(rows, "A24110"):
                    if await _save_cs(db, material, r, ("A20000", "01", "00"), user):
                        done.append("CF-007")
            if "CF-012" not in leave:
                for r in _row(rows, "A22140", "02"):
                    if r.article_reference_id is None and r.article_id:
                        values = {n: getattr(r, n) for n in confunfis.FIELDS}
                        await confunfis.save_row(db, material, values, user.id, source=r.source, strict=False, row=r,
                                                 identity={"article_id": r.article_id, "pn": CAP_PN, "ncage": CAP_NCAGE})
                        done.append("CF-012")
            if "CF-014" not in leave:
                for r in _row(rows, "D53000"):
                    if not (r.function_text or "").strip():
                        values = {**{n: getattr(r, n) for n in confunfis.FIELDS}, "function_text": HARNESS_FUNCTION}
                        await confunfis.save_row(db, material, values, user.id, source=r.source, strict=False, row=r)
                        done.append("CF-014")
            if "CF-015" not in leave:
                for r in _row(rows, "B32020")[1:]:
                    await confunfis.delete_row(db, material, r, user.id)
                    done.append("CF-015")
            if "PF-001" not in leave:
                for p in await extras.live_products(db, material.id):
                    if p.supply_unit == "ZZ":
                        values = {f: getattr(p, f) for f in ("designation", "pol_code", "nae", "noc", "quantity", "unit")} | {"supply_unit": "DR"}
                        await extras.save_product(db, material, values, user.id, source=p.source, product=p)
                        done.append("PF-001")
            if "AR-002" not in leave and (tank := article_named("DEPÓSITO DE EXPANSIÓN")) is not None:
                if data_of(tank).get("snRepaArt") == "S" and not any(data_of(tank).get(level) == "S" for level in LEVELS):
                    if await _edit_article(db, tank, {LEVELS[-1]: "S"}, user):
                        done.append("AR-002")
            if "AR-003" not in leave and (coupling := article_named("ACOPLAMIENTO VISCOSO")) is not None:
                if data_of(coupling).get("caPesoArt") is not None and not data_of(coupling).get("cdUnidPesoArt"):
                    if await _edit_article(db, coupling, {"cdUnidPesoArt": "KG"}, user):
                        done.append("AR-003")
            if "AR-006" not in leave and (rod := article_named("BIELA DM-6")) is not None:
                if data_of(rod).get("snMtPreArt") == "S" and data_of(rod).get("snCtrlVidaArt") != "S":
                    unit = sorted(c for c, active in (await codes_by_state(db, "D114")).items() if active)[0]
                    if await _edit_article(db, rod, {"snCtrlVidaArt": "S"}, user, [LifeControl(unit, Decimal("20000"))]):
                        done.append("AR-006")
            await db.flush()
            await confunfis.refresh_materials(db, article_ids=set(articles), material_ids={material.id})
            await extras.refresh_products(db, material)
        await db.commit()
    await engine.dispose()
    print(f"Corregidos: {', '.join(done) or 'nada (ya estaba)'}." + (f" Sin corregir a propósito: {', '.join(sorted(leave))}." if leave else ""))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dejar", nargs="*", default=[], choices=CODES, help="hallazgos que se dejan sin corregir (p. ej. CF-007)")
    args = parser.parse_args()
    if get_settings().environment == "production":
        print("No se ejecuta con ENVIRONMENT=production.", file=sys.stderr)
        return 1
    return asyncio.run(run(set(args.dejar)))


if __name__ == "__main__":
    utf8_output()
    sys.exit(cancellable(main))
