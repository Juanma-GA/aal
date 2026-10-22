"""A deactivated or deleted user cannot get in, and loses the sessions they
had; a pending password change blocks everything but the change."""

from helpers import TEST_PASSWORD, bearer, login


async def test_deactivated_user_loses_access_and_session(client, factory):
    admin = await factory.user(is_admin=True)
    user = await factory.user()
    admin_token, _ = await login(client, admin)
    client.cookies.clear()
    user_token, res = await login(client, user)
    raw = res.cookies["aal_refresh"]
    res = await client.patch(f"/api/users/{user.id}", json={"version": 1, "is_active": False}, headers=bearer(admin_token))
    assert res.status_code == 200, res.text
    assert (await client.get("/api/auth/me", headers=bearer(user_token))).status_code == 401
    client.cookies.clear()
    client.cookies.set("aal_refresh", raw, domain="aal.test", path="/api/auth")
    assert (await client.post("/api/auth/refresh")).status_code == 401
    res = await client.post("/api/auth/login", json={"email": user.email, "password": TEST_PASSWORD})
    assert res.status_code == 401


async def test_deleted_user_loses_access_and_session(client, factory):
    admin = await factory.user(is_admin=True)
    user = await factory.user()
    admin_token, _ = await login(client, admin)
    client.cookies.clear()
    user_token, res = await login(client, user)
    raw = res.cookies["aal_refresh"]
    assert (await client.delete(f"/api/users/{user.id}?confirm=true", headers=bearer(admin_token))).status_code == 204
    assert (await client.get("/api/auth/me", headers=bearer(user_token))).status_code == 401
    client.cookies.clear()
    client.cookies.set("aal_refresh", raw, domain="aal.test", path="/api/auth")
    assert (await client.post("/api/auth/refresh")).status_code == 401
    assert (await client.post("/api/auth/login", json={"email": user.email, "password": TEST_PASSWORD})).status_code == 401


async def test_pending_password_change_blocks_everything_but_the_change(client, factory):
    user = await factory.user(must_change_password=True)
    token, _ = await login(client, user)
    me = await client.get("/api/auth/me", headers=bearer(token))
    assert me.status_code == 200 and me.json()["must_change_password"] is True
    blocked = await client.get("/api/materials", headers=bearer(token))
    assert blocked.status_code == 403 and blocked.json()["detail"]["code"] == "password_change_required"
    res = await client.post(
        "/api/me/password", json={"current_password": TEST_PASSWORD, "new_password": "Una-contraseña-nueva-9"}, headers=bearer(token)
    )
    assert res.status_code == 200, res.text
    # The old access token keeps its short life; the new one is in the answer.
    new_token = res.json()["access_token"]
    assert (await client.get("/api/materials", headers=bearer(new_token))).status_code == 200
