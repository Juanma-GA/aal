"""Shared pytest setup for the backend tests.

The tests never run on the app's database: before anything imports the app,
tests/_testdb.py resolves TEST_DATABASE_URL (environment or backend/.env)
and refuses -- one message, no test runs -- if it is missing, does not end
in "_test", or is the app's own DATABASE_URL. Then it becomes the
DATABASE_URL of this process, so the app's settings, its engine and every
subprocess a test starts (they inherit the environment) use the test
database. This holds for `npm run test:backend` and for a hand-run pytest.
"""

import os

import pytest

from _testdb import TestDatabaseRefused, resolve_test_database

try:
    _TEST_DB = resolve_test_database()
    _REFUSED = None
except TestDatabaseRefused as exc:
    _TEST_DB = None
    _REFUSED = str(exc)


def pytest_configure(config):
    """Stops the whole run with one line when the test database is missing
    or must not be used (before any test module is imported)."""
    if _REFUSED:
        raise pytest.UsageError(f"Backend tests not run: {_REFUSED}")


if _TEST_DB is not None:
    os.environ["DATABASE_URL"] = _TEST_DB.url

    import pytest_asyncio  # noqa: E402
    from httpx import ASGITransport, AsyncClient  # noqa: E402

    from app.core.config import get_settings  # noqa: E402

    get_settings.cache_clear()  # in case anything read the settings before the line above

    from app.db.base import async_session_factory, engine  # noqa: E402
    from app.main import app  # noqa: E402

    if get_settings().database_url != _TEST_DB.url:
        raise RuntimeError("the app is not using the test database")

    @pytest_asyncio.fixture
    async def client():
        """Real HTTP-shaped client against the actual FastAPI app -- no
        mocking of the DB layer. Needs the test database reachable and
        migrated: `npm run test:db:create`."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

    @pytest_asyncio.fixture
    async def db():
        """A session on the test database. What a test commits stays; a
        test cleans up the rows it creates."""
        async with async_session_factory() as session:
            yield session

    @pytest_asyncio.fixture(autouse=True)
    async def _dispose_engine_after_test():
        """app/db/base.py's engine is a module-level singleton -- right for
        the app (one event loop for its whole life), but pytest-asyncio gives
        each test its own loop. Disposing the pool after every test makes the
        next one open fresh connections on its own loop instead of failing
        with "attached to a different loop"."""
        yield
        await engine.dispose()
