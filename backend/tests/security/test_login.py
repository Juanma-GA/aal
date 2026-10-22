"""Login: right and wrong credentials, the same answer for every wrong case,
and the limit of failed attempts per email and per address."""

from sqlalchemy import func, select

from app.db.base import async_session_factory
from app.models import LoginFailure
from app.services.parameters import PARAMETER_DEFAULTS
from helpers import TEST_PASSWORD, bearer, login

LIMIT = PARAMETER_DEFAULTS["auth"]["login_limit"]


async def test_correct_login_gives_a_token_and_a_cookie(client, factory):
    user = await factory.user()
    token, res = await login(client, user)
    body = res.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == PARAMETER_DEFAULTS["auth"]["access_token_minutes"] * 60
    assert "aal_refresh" in res.cookies
    me = await client.get("/api/auth/me", headers=bearer(token))
    assert me.status_code == 200 and me.json()["email"] == user.email
    assert "password_hash" not in me.text


async def test_email_is_case_insensitive(client, factory):
    user = await factory.user()
    await login(client, user.email.upper())


async def test_wrong_password_unknown_email_inactive_and_deleted_answer_the_same(client, factory):
    from datetime import UTC, datetime

    from app.models import User

    user = await factory.user()
    inactive = await factory.user(is_active=False)
    deleted = await factory.user()
    async with async_session_factory() as session:
        row = await session.get(User, deleted.id)
        row.deleted_at = datetime.now(UTC)
        await session.commit()
    answers = []
    for email, password in (
        (user.email, "otra-contraseña-mala"),
        ("nadie@aal-test.es", TEST_PASSWORD),
        (inactive.email, TEST_PASSWORD),
        (deleted.email, TEST_PASSWORD),
    ):
        res = await client.post("/api/auth/login", json={"email": email, "password": password})
        answers.append((res.status_code, res.json()))
        assert "aal_refresh" not in res.cookies
    assert all(a == (401, {"detail": {"code": "invalid_credentials"}}) for a in answers), answers


async def test_too_many_failures_for_an_email_lock_it_even_with_the_right_password(client, factory):
    user = await factory.user()
    for _ in range(LIMIT["max_failures_per_email"]):
        res = await client.post("/api/auth/login", json={"email": user.email, "password": "mala-mala-mala"})
        assert res.status_code == 401
    res = await client.post("/api/auth/login", json={"email": user.email, "password": TEST_PASSWORD})
    assert res.status_code == 429
    detail = res.json()["detail"]
    assert detail["code"] == "login_rate_limited"
    assert 1 <= detail["retry_after_minutes"] <= LIMIT["window_minutes"]
    assert int(res.headers["Retry-After"]) == detail["retry_after_minutes"] * 60
    # Another account from the same address is still allowed.
    other = await factory.user()
    await login(client, other)


async def test_too_many_failures_from_one_address_lock_it(client, factory):
    for i in range(LIMIT["max_failures_per_ip"]):
        res = await client.post("/api/auth/login", json={"email": f"nadie{i}@aal-test.es", "password": "x"})
        assert res.status_code == 401
    user = await factory.user()
    res = await client.post("/api/auth/login", json={"email": user.email, "password": TEST_PASSWORD})
    assert res.status_code == 429


async def test_a_successful_login_clears_the_failures_of_the_email(client, factory):
    user = await factory.user()
    for _ in range(LIMIT["max_failures_per_email"] - 1):
        await client.post("/api/auth/login", json={"email": user.email, "password": "mala"})
    await login(client, user)
    async with async_session_factory() as session:
        left = await session.scalar(select(func.count()).select_from(LoginFailure).where(LoginFailure.email == user.email))
    assert left == 0


async def test_unexpected_fields_are_refused_without_echoing_values(client, factory):
    user = await factory.user()
    res = await client.post("/api/auth/login", json={"email": user.email, "password": "secreto-que-no-vuelve", "admin": True})
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "validation_error"
    assert "secreto-que-no-vuelve" not in res.text
