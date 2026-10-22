"""The Panel's data (E02): a material's team and recent activity, for
whoever may see the material, and nothing more."""

from helpers import bearer, login


async def test_team_and_activity_for_members_404_for_others(client, factory):
    material = await factory.material()
    other = await factory.material()
    analyst = await factory.user(name="Ana Lista")
    observer = await factory.user(name="Obdulia Servadora")
    await factory.assign(analyst, material, "analista")
    await factory.assign(observer, material, "observador")
    admin_token, _ = await login(client, await factory.user(is_admin=True))
    await client.patch(f"/api/materials/{material.id}", json={"version": 1, "name": "Renombrado"}, headers=bearer(admin_token))
    client.cookies.clear()
    token, _ = await login(client, observer)
    h = bearer(token)

    team = (await client.get(f"/api/materials/{material.id}/members", headers=h)).json()
    assert team == [{"display_name": "Ana Lista", "role": "analista"}, {"display_name": "Obdulia Servadora", "role": "observador"}]

    activity = (await client.get(f"/api/materials/{material.id}/activity", headers=h)).json()
    assert activity and activity[0]["action"] == "material.updated"
    assert set(activity[0]) == {"created_at", "action", "entity_type", "user_name"}  # no before / after
    for url in (f"/api/materials/{other.id}/members", f"/api/materials/{other.id}/activity"):
        res = await client.get(url, headers=h)
        assert res.status_code == 404 and res.json()["detail"]["code"] == "material_not_found"


async def test_the_admin_sees_the_members_full(client, factory):
    material = await factory.material()
    member = await factory.user()
    await factory.assign(member, material, "revisor")
    token, _ = await login(client, await factory.user(is_admin=True))
    (row,) = (await client.get(f"/api/materials/{material.id}/members", headers=bearer(token))).json()
    assert row["email"] == member.email and row["user_id"] == str(member.id) and row["assigned_at"]


async def test_activity_is_limited_by_the_parameter(client, factory):
    from app.services.parameters import PARAMETER_DEFAULTS

    material = await factory.material()
    admin_token, _ = await login(client, await factory.user(is_admin=True))
    h = bearer(admin_token)
    version = 1
    for i in range(PARAMETER_DEFAULTS["panel"]["activity_items"] + 2):
        res = await client.patch(f"/api/materials/{material.id}", json={"version": version, "name": f"Nombre {i}"}, headers=h)
        version = res.json()["version"]
    activity = (await client.get(f"/api/materials/{material.id}/activity", headers=h)).json()
    assert len(activity) == PARAMETER_DEFAULTS["panel"]["activity_items"]


async def test_sidebar_groups_are_kept_in_ui_preferences(client, factory):
    token, _ = await login(client, await factory.user())
    h = bearer(token)
    res = await client.put("/api/me/ui-preferences", json={"sidebar_collapsed_groups": ["pramt", "pman"]}, headers=h)
    assert res.json()["ui_preferences"]["sidebar_collapsed_groups"] == ["pramt", "pman"]
    res = await client.put("/api/me/ui-preferences", json={"sidebar_collapsed_groups": ["pman"]}, headers=h)
    assert res.json()["ui_preferences"]["sidebar_collapsed_groups"] == ["pman"]
    assert (await client.put("/api/me/ui-preferences", json={"sidebar_collapsed_groups": ["x" * 51]}, headers=h)).status_code == 422
