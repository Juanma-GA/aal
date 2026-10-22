"""The reference tables in the database (E03): what migration 0004 loaded,
and reloads that add what is new without touching an admin's edits."""

from dataclasses import replace

from sqlalchemy import func, select, update

from app.db.base import engine
from app.models import ArticleFieldDefinition, ReferenceTable, ReferenceValue
from app.services.reference_seed import SeedTable, SeedValue, load_reference_tables, read_seed
from unit.test_reference_seed import COUNTS


async def test_the_migration_loaded_the_tables_and_the_fields(db):
    rows = await db.execute(select(ReferenceValue.table_code, func.count()).group_by(ReferenceValue.table_code))
    assert dict(rows.all()) == COUNTS
    assert await db.scalar(select(func.count()).select_from(ReferenceTable)) == 15
    assert await db.scalar(select(func.count()).select_from(ArticleFieldDefinition)) == 30
    def codes(table):
        return db.execute(select(ReferenceValue.code).where(ReferenceValue.table_code == table))

    assert {"0", "1"} <= set((await codes("D107")).scalars())
    d114 = set((await codes("D114")).scalars())
    assert {"01", "02", "09"} <= d114 and not {"1", "2", "9"} & d114
    field = await db.get(ArticleFieldDefinition, "cdConjRep")
    assert (field.name, field.reference_table_code, field.length) == ("Grupo estructural", "D107", 1)


async def test_reload_is_idempotent_and_never_overwrites_an_admins_edit():
    seed = read_seed()
    changed = replace(
        seed,
        tables=[
            replace(t, values=t.values + [SeedValue("ZZ", "Nueva del semillero", None, {})]) if t.code == "D112" else t
            for t in seed.tables
        ]
        + [SeedTable("PRUEBA", "Tabla de prueba", "test", None, [], [SeedValue("1", "Uno", None, {})])],
    )
    async with engine.connect() as conn:
        trans = await conn.begin()
        try:
            again = await conn.run_sync(load_reference_tables)
            assert (again.tables_added, again.values_added, again.fields_added, again.fields_updated) == (0, 0, 0, 0)
            assert again.differences == [] and again.values_not_in_seed == []
            # An admin edits a description; the reload keeps it and says so.
            await conn.execute(
                update(ReferenceValue).where(ReferenceValue.table_code == "D112", ReferenceValue.code == "EA").values(description="Editada")
            )
            report = await conn.run_sync(load_reference_tables, changed)
            assert (report.tables_added, report.values_added) == (1, 2)
            assert [(d.table, d.code, d.field, d.stored) for d in report.differences] == [("D112", "EA", "description", "Editada")]
            ea = (await conn.execute(select(ReferenceValue.description).where(ReferenceValue.table_code == "D112", ReferenceValue.code == "EA"))).scalar()
            assert ea == "Editada"
            zz = (await conn.execute(select(ReferenceValue).where(ReferenceValue.table_code == "D112", ReferenceValue.code == "ZZ"))).one()
            assert zz.sort_order == 83 and zz.is_active
            # The original seed again: the value it no longer has is kept.
            back = await conn.run_sync(load_reference_tables)
            assert "D112/ZZ" in back.values_not_in_seed
        finally:
            await trans.rollback()
