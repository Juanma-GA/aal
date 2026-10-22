"""Puts reference tables back as they were after a test that edits them:
values the test added are removed (only tests delete), the rest get their
stored columns back, and the table its version."""

import pytest_asyncio
from sqlalchemy import delete, select, update

from app.db.base import async_session_factory
from app.models import ReferenceTable, ReferenceValue

_COLUMNS = ("description", "definition", "attributes", "is_active", "sort_order", "version")


@pytest_asyncio.fixture
async def restore_tables():
    saved: dict[str, tuple[int, dict]] = {}

    async def keep(*codes: str) -> None:
        async with async_session_factory() as session:
            for code in codes:
                table = await session.get(ReferenceTable, code)
                values = (await session.execute(select(ReferenceValue).where(ReferenceValue.table_code == code))).scalars()
                saved[code] = (table.version, {v.id: {c: getattr(v, c) for c in _COLUMNS} for v in values})

    yield keep
    async with async_session_factory() as session:
        for code, (version, values) in saved.items():
            await session.execute(delete(ReferenceValue).where(ReferenceValue.table_code == code, ReferenceValue.id.not_in(list(values))))
            for value_id, columns in values.items():
                await session.execute(update(ReferenceValue).where(ReferenceValue.id == value_id).values(**columns))
            await session.execute(update(ReferenceTable).where(ReferenceTable.code == code).values(version=version))
        await session.commit()
