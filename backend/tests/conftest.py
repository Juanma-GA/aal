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
        # https: the refresh cookie is Secure, and a client only sends it
        # back over https.
        async with AsyncClient(transport=transport, base_url="https://aal.test") as ac:
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

    # ── Helpers for the auth / roles tests (E01) ──────────────────────────
    import uuid as _uuid  # noqa: E402

    from sqlalchemy import delete as _delete  # noqa: E402
    from sqlalchemy import update as _update  # noqa: E402

    from app.core.security import hash_password as _hash_password  # noqa: E402
    from app.models import LoginFailure, Material, User, UserMaterialRole  # noqa: E402

    TEST_PASSWORD = "Contraseña-de-prueba-1"
    # One bcrypt hash for every test user: hashing is slow on purpose.
    _TEST_HASH = _hash_password(TEST_PASSWORD)

    class Factory:
        """Creates users, materials and roles straight in the test database
        and deletes them (and their failed logins) after the test."""

        def __init__(self):
            self.user_ids: list = []
            self.material_ids: list = []

        async def user(self, *, is_admin=False, is_active=True, must_change_password=False, email=None, name="Usuario de prueba"):
            email = email or f"t-{_uuid.uuid4().hex[:12]}@aal-test.es"
            async with async_session_factory() as session:
                user = User(
                    email=email,
                    display_name=name,
                    password_hash=_TEST_HASH,
                    is_admin=is_admin,
                    is_active=is_active,
                    must_change_password=must_change_password,
                    ui_preferences={},
                    version=1,
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)
            self.user_ids.append(user.id)
            return user

        async def material(self, name=None, **fields):
            async with async_session_factory() as session:
                material = Material(name=name or f"Material de prueba {_uuid.uuid4().hex[:6]}", version=1, **fields)
                session.add(material)
                await session.commit()
                await session.refresh(material)
            self.material_ids.append(material.id)
            return material

        async def assign(self, user, material, role):
            async with async_session_factory() as session:
                session.add(UserMaterialRole(user_id=user.id, material_id=material.id, role_code=role))
                await session.commit()

        async def cleanup(self):
            async with async_session_factory() as session:
                await session.execute(_delete(LoginFailure))
                if self.material_ids:
                    await session.execute(_delete(Material).where(Material.id.in_(self.material_ids)))
                if self.user_ids:
                    await session.execute(_update(User).where(User.id.in_(self.user_ids)).values(deleted_by=None))
                    await session.execute(_update(Material).where(Material.deleted_by.in_(self.user_ids)).values(deleted_by=None))
                    await session.execute(
                        _update(UserMaterialRole).where(UserMaterialRole.assigned_by.in_(self.user_ids)).values(assigned_by=None)
                    )
                    await session.execute(_delete(User).where(User.id.in_(self.user_ids)))
                await session.commit()

    @pytest_asyncio.fixture
    async def factory():
        made = Factory()
        yield made
        await made.cleanup()

    async def login(client, user_or_email, password=TEST_PASSWORD):
        """Signs in; returns (access token, the response)."""
        email = user_or_email if isinstance(user_or_email, str) else user_or_email.email
        res = await client.post("/api/auth/login", json={"email": email, "password": password})
        assert res.status_code == 200, res.text
        return res.json()["access_token"], res

    def bearer(token):
        return {"Authorization": f"Bearer {token}"}

    @pytest_asyncio.fixture(autouse=True)
    async def _no_login_failures_left():
        """Failed logins of one test never count in the next one (the per
        address limit is shared: every test client is 127.0.0.1)."""
        yield
        async with async_session_factory() as session:
            await session.execute(_delete(LoginFailure))
            await session.commit()
