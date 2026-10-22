"""The catalog in the database (E02): what migration 0003 loaded, and
reloads that add and update without touching an admin's status."""

from dataclasses import replace

from sqlalchemy import func, select, update

from app.db.base import engine
from app.models import ModuleCatalog, ModuleGroup, ModuleRequirement
from app.services.module_catalog import REQUIRED_RF, SeedModule, load_catalog, read_seed


async def test_the_migration_loaded_the_catalog(db):
    assert await db.scalar(select(func.count()).select_from(ModuleGroup)) == 9
    assert await db.scalar(select(func.count()).select_from(ModuleCatalog)) == 45
    rfs = set((await db.execute(select(ModuleRequirement.rf_id))).scalars().all())
    assert rfs >= set(REQUIRED_RF)
    panel = await db.get(ModuleCatalog, "panel")
    assert (panel.status, panel.route) == ("disponible", "/materiales/:materialId")


async def test_reload_keeps_an_admins_status_updates_texts_and_adds_new():
    seed = read_seed()
    changed = replace(
        seed,
        modules=[replace(m, objective="Texto nuevo") if m.code == "fta" else m for m in seed.modules]
        + [
            SeedModule(
                code="modulo-de-prueba", group_code="transversal", name="Módulo de prueba", sort_order=99, phase="4",
                status="planificado", encargo=None, objective="", inputs=[], outputs=[], deliverable=None,
                dependencies=["fta"], route=None, requirements=[],
            )
        ],
    )
    async with engine.connect() as conn:
        trans = await conn.begin()
        try:
            await conn.execute(update(ModuleCatalog).where(ModuleCatalog.code == "fta").values(status="en_desarrollo"))
            report = await conn.run_sync(load_catalog, changed)
            fta = (await conn.execute(select(ModuleCatalog).where(ModuleCatalog.code == "fta"))).one()
            new = (await conn.execute(select(ModuleCatalog).where(ModuleCatalog.code == "modulo-de-prueba"))).one()
            assert fta.status == "en_desarrollo"  # an admin's change survives
            assert fta.objective == "Texto nuevo"  # the text is the seed's
            assert new.status == "planificado"
            assert (report.modules_added, report.modules_updated) == (1, 1)
            again = await conn.run_sync(load_catalog, changed)
            assert (again.modules_added, again.modules_updated) == (0, 0)  # idempotent
        finally:
            await trans.rollback()
    await engine.dispose()


async def test_a_module_that_left_the_seed_is_kept_and_reported():
    seed = read_seed()
    fewer = replace(seed, modules=[m for m in seed.modules if m.code != "teamcenter"] + [
        replace(next(m for m in seed.modules if m.code == "teamcenter"), code="teamcenter-2")
    ])
    async with engine.connect() as conn:
        trans = await conn.begin()
        try:
            report = await conn.run_sync(load_catalog, fewer)
            assert report.modules_not_in_seed == ["teamcenter"]
            assert (await conn.execute(select(ModuleCatalog.code).where(ModuleCatalog.code == "teamcenter"))).first()
        finally:
            await trans.rollback()
    await engine.dispose()
