"""The refresh token: cookie attributes, rotation, reuse detection (the
whole family revoked) and logout."""

from sqlalchemy import select

from app.db.base import async_session_factory
from app.models import RefreshToken
from app.services.parameters import PARAMETER_DEFAULTS
from helpers import login


def _cookie_header(res) -> str:
    headers = [v for k, v in res.headers.multi_items() if k.lower() == "set-cookie" and v.startswith("aal_refresh=")]
    assert len(headers) == 1, headers
    return headers[0]


def _use(client, raw):
    client.cookies.clear()
    client.cookies.set("aal_refresh", raw, domain="aal.test", path="/api/auth")


async def _refresh_with(client, raw):
    _use(client, raw)
    return await client.post("/api/auth/refresh")


async def test_cookie_attributes(client, factory):
    user = await factory.user()
    _token, res = await login(client, user)
    header = _cookie_header(res)
    parts = [p.strip().lower() for p in header.split(";")]
    assert "httponly" in parts
    assert "secure" in parts
    assert "samesite=strict" in parts
    assert "path=/api/auth" in parts
    assert f"max-age={PARAMETER_DEFAULTS['auth']['refresh_token_days'] * 86400}" in parts
    # The access token never travels in a cookie.
    assert all(not v.startswith("access") for k, v in res.headers.multi_items() if k.lower() == "set-cookie")


async def test_only_a_hash_of_the_refresh_token_is_stored(client, factory):
    user = await factory.user()
    _token, res = await login(client, user)
    raw = res.cookies["aal_refresh"]
    async with async_session_factory() as session:
        hashes = (await session.execute(select(RefreshToken.token_hash).where(RefreshToken.user_id == user.id))).scalars().all()
    assert hashes and raw not in hashes and all(len(h) == 64 for h in hashes)


async def test_refresh_rotates_the_token(client, factory):
    user = await factory.user()
    _token, res = await login(client, user)
    first = res.cookies["aal_refresh"]
    res = await _refresh_with(client, first)
    assert res.status_code == 200 and res.json()["access_token"]
    second = res.cookies["aal_refresh"]
    assert second != first
    res = await _refresh_with(client, second)
    assert res.status_code == 200


async def test_reusing_a_rotated_token_revokes_the_whole_family(client, factory):
    user = await factory.user()
    _token, res = await login(client, user)
    first = res.cookies["aal_refresh"]
    second = (await _refresh_with(client, first)).cookies["aal_refresh"]
    # Someone replays the first (already rotated) token.
    res = await _refresh_with(client, first)
    assert res.status_code == 401
    assert res.json()["detail"]["code"] == "session_revoked"
    # ... and the legitimate holder of the second one is out too.
    res = await _refresh_with(client, second)
    assert res.status_code == 401
    async with async_session_factory() as session:
        reasons = (await session.execute(select(RefreshToken.revoke_reason).where(RefreshToken.user_id == user.id))).scalars().all()
    assert set(reasons) == {"rotated", "reuse_detected"}


async def test_reuse_in_one_family_leaves_other_sessions_alone(client, factory):
    user = await factory.user()
    _t, res_a = await login(client, user)
    a1 = res_a.cookies["aal_refresh"]
    client.cookies.clear()
    _t, res_b = await login(client, user)
    b1 = res_b.cookies["aal_refresh"]
    await _refresh_with(client, a1)
    await _refresh_with(client, a1)  # reuse in family A
    assert (await _refresh_with(client, b1)).status_code == 200


async def test_logout_revokes_the_session(client, factory):
    user = await factory.user()
    _token, res = await login(client, user)
    raw = res.cookies["aal_refresh"]
    _use(client, raw)
    out = await client.post("/api/auth/logout")
    assert out.status_code == 204
    cleared = _cookie_header(out).lower()
    assert "max-age=0" in cleared or "expires=" in cleared
    assert (await _refresh_with(client, raw)).status_code == 401


async def test_logout_without_a_session_is_fine(client):
    client.cookies.clear()
    assert (await client.post("/api/auth/logout")).status_code == 204


async def test_refresh_without_cookie_or_with_an_unknown_one(client):
    client.cookies.clear()
    assert (await client.post("/api/auth/refresh")).json()["detail"]["code"] == "session_expired"
    assert (await _refresh_with(client, "inventado")).status_code == 401
