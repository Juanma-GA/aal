"""alembic upgrade head creates app_parameter and audit_log; downgrade base
drops them (E00, criterion 2). Runs on the test database and leaves it at
head."""
import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import inspect

from app.db.base import engine

BACKEND = Path(__file__).resolve().parents[2]
TABLES = {"app_parameter", "audit_log"}


def _alembic(*args: str) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")


async def _tables() -> set[str]:
    async with engine.connect() as conn:
        names = await conn.run_sync(lambda sync: set(inspect(sync).get_table_names()))
    await engine.dispose()
    return names


async def test_downgrade_base_drops_and_upgrade_head_recreates():
    assert TABLES <= await _tables()
    try:
        _alembic("downgrade", "base")
        assert not (TABLES & await _tables())
    finally:
        _alembic("upgrade", "head")
    assert TABLES <= await _tables()
