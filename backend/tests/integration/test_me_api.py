"""/api/me/password and /api/me/ui-preferences."""

from helpers import TEST_PASSWORD, bearer, login


async def test_password_change_rules(client, factory):
    user = await factory.user()
    token, _ = await login(client, user)
    h = bearer(token)
    res = await client.post("/api/me/password", json={"current_password": "mala", "new_password": "Una-buena-de-verdad-1"}, headers=h)
    assert res.status_code == 403 and res.json()["detail"]["code"] == "current_password_incorrect"
    res = await client.post("/api/me/password", json={"current_password": TEST_PASSWORD, "new_password": "corta"}, headers=h)
    assert res.json()["detail"] == {"code": "password_too_short", "min_length": 12}
    res = await client.post("/api/me/password", json={"current_password": TEST_PASSWORD, "new_password": "ñ" * 40}, headers=h)
    assert res.json()["detail"] == {"code": "password_too_long", "max_bytes": 72}
    res = await client.post("/api/me/password", json={"current_password": TEST_PASSWORD, "new_password": TEST_PASSWORD}, headers=h)
    assert res.json()["detail"]["code"] == "password_unchanged"


async def test_password_change_ends_other_sessions_and_opens_a_new_one(client, factory):
    user = await factory.user()
    _t, other = await login(client, user)
    other_cookie = other.cookies["aal_refresh"]
    client.cookies.clear()
    token, _ = await login(client, user)
    res = await client.post(
        "/api/me/password", json={"current_password": TEST_PASSWORD, "new_password": "Otra-contraseña-larga-2"}, headers=bearer(token)
    )
    assert res.status_code == 200 and res.json()["access_token"]
    assert (await client.post("/api/auth/refresh")).status_code == 200  # the new cookie of this session
    client.cookies.clear()
    client.cookies.set("aal_refresh", other_cookie, domain="aal.test", path="/api/auth")
    assert (await client.post("/api/auth/refresh")).status_code == 401  # the other session is over
    client.cookies.clear()
    await login(client, user, "Otra-contraseña-larga-2")


async def test_ui_preferences_are_deep_merged_and_checked(client, factory):
    user = await factory.user()
    mine = await factory.material()
    other = await factory.material()
    await factory.assign(user, mine, "analista")
    token, _ = await login(client, user)
    h = bearer(token)
    res = await client.put("/api/me/ui-preferences", json={"active_material_id": str(mine.id)}, headers=h)
    assert res.status_code == 200 and res.json()["ui_preferences"] == {"active_material_id": str(mine.id)}
    assert (await client.get("/api/auth/me", headers=h)).json()["ui_preferences"]["active_material_id"] == str(mine.id)
    res = await client.put("/api/me/ui-preferences", json={"active_material_id": str(other.id)}, headers=h)
    assert res.status_code == 404 and res.json()["detail"]["code"] == "material_not_found"
    assert (await client.put("/api/me/ui-preferences", json={"theme": "dark"}, headers=h)).status_code == 422
    # An empty body keeps what is stored (deep merge, nothing dropped).
    res = await client.put("/api/me/ui-preferences", json={}, headers=h)
    assert res.json()["ui_preferences"] == {"active_material_id": str(mine.id)}
    res = await client.put("/api/me/ui-preferences", json={"active_material_id": None}, headers=h)
    assert res.json()["ui_preferences"] == {"active_material_id": None}
