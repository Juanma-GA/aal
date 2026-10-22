from functools import lru_cache
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncConnection

# backend/alembic.ini, from this file's path: independent of the cwd.
_BACKEND = Path(__file__).resolve().parents[2]


@lru_cache
def alembic_head() -> str | None:
    """The latest revision the code defines (alembic/versions/), read from
    the migration scripts without touching the database (once: the scripts
    do not change while the process runs)."""
    cfg = Config(str(_BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(_BACKEND / "alembic"))
    return ScriptDirectory.from_config(cfg).get_current_head()


async def migration_status(conn: AsyncConnection) -> dict:
    """The database's applied revision against the code's head.

    A never-migrated database (no alembic_version table) reads as
    current=None. A database that cannot be reached raises: the caller
    turns that into a sanitized 503 (app/core/errors.py), never a guess.
    """
    head = alembic_head()
    try:
        async with conn.begin_nested():
            row = (await conn.execute(text("SELECT version_num FROM alembic_version"))).first()
        current = row[0] if row else None
    except ProgrammingError:
        current = None
    return {"current": current, "head": head, "up_to_date": current == head}
