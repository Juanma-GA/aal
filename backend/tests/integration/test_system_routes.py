"""GET /api/health and GET /api/version against the real app and the test
database; and /api/health with the database down: a sanitized 503."""
import logging

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.migrations import alembic_head
from app.db.base import get_db
from app.main import app
from app.version import aacf_version, app_version

# Port 1 on loopback: nothing listens there, the connection is refused.
DOWN_URL = "postgresql+asyncpg://aal:aal@127.0.0.1:1/aal_test"


async def test_health_reports_database_and_migration(client):
    res = await client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["database"]["status"] == "ok"
    assert body["database"]["migrations"] == {"current": alembic_head(), "head": alembic_head(), "up_to_date": True}


async def test_version_reports_app_and_aacf(client):
    res = await client.get("/api/version")
    assert res.status_code == 200
    assert res.json() == {"app": app_version(), "aacf": aacf_version()}
    assert res.json()["aacf"]


@pytest_asyncio.fixture
async def client_with_database_down():
    engine = create_async_engine(DOWN_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def down_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = down_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_db, None)
        await engine.dispose()


async def test_health_with_database_down_is_sanitized(client_with_database_down, caplog):
    with caplog.at_level(logging.ERROR, logger="app.errors"):
        res = await client_with_database_down.get("/api/health")
    assert res.status_code == 503
    detail = res.json()["detail"]
    assert detail["code"] == "database_unavailable"
    assert len(detail["ref"]) == 8
    assert set(detail) == {"code", "ref"}
    # Nothing technical reaches the client ...
    text = res.text.lower()
    for leak in ("traceback", "refused", "errno", "asyncpg", "127.0.0.1", "oserror", "connect"):
        assert leak not in text, leak
    # ... it is all in the log, under the same reference.
    logged = [r for r in caplog.records if getattr(r, "ref", None) == detail["ref"]]
    assert logged and logged[0].exc_info is not None


async def test_unexpected_error_is_a_sanitized_500(client, caplog):
    async def broken():
        raise RuntimeError("secret internal detail")

    app.add_api_route("/api/_test_broken", broken)
    try:
        with caplog.at_level(logging.ERROR, logger="app.errors"):
            res = await client.get("/api/_test_broken")
    finally:
        app.router.routes = [r for r in app.router.routes if getattr(r, "path", None) != "/api/_test_broken"]
    assert res.status_code == 500
    assert res.json()["detail"]["code"] == "internal_error"
    assert "secret internal detail" not in res.text
    assert any("secret internal detail" in (r.exc_text or str(r.exc_info)) for r in caplog.records if r.exc_info)


def test_a_file_error_is_not_reported_as_the_database():
    from app.core.errors import is_database_unavailable

    assert is_database_unavailable(ConnectionRefusedError())
    assert is_database_unavailable(TimeoutError())
    assert not is_database_unavailable(FileNotFoundError())
    assert not is_database_unavailable(PermissionError())
