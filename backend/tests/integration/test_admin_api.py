"""/api/roles, /api/audit (+ facets) and /api/parameters."""

import uuid
from datetime import UTC, datetime, timedelta

from app.services.parameters import PARAMETER_DEFAULTS
from helpers import bearer, login


async def test_roles_matrix_is_readable_by_any_signed_in_user(client, factory):
    user = await factory.user()
    token, _ = await login(client, user)
    body = (await client.get("/api/roles", headers=bearer(token))).json()
    assert [r["code"] for r in body["roles"]] == ["analista", "revisor", "observador"]
    assert body["permissions"][0] == {"code": "material.ver", "area": "material"}
    assert "revision.aprobar" in body["matrix"]["revisor"] and "revision.aprobar" not in body["matrix"]["analista"]


async def test_audit_filters_and_pages(client, factory):
    admin = await factory.user(is_admin=True)
    token, _ = await login(client, admin)
    h = bearer(token)
    material = (await client.post("/api/materials", json={"name": f"Auditado {uuid.uuid4().hex[:6]}"}, headers=h)).json()
    factory.material_ids.append(uuid.UUID(material["id"]))
    await client.patch(f"/api/materials/{material['id']}", json={"version": 1, "name": "Auditado 2"}, headers=h)
    page = (await client.get("/api/audit", params={"material_id": material["id"]}, headers=h)).json()
    assert page["total"] == 2 and [i["action"] for i in page["items"]] == ["material.updated", "material.created"]
    item = page["items"][0]
    assert item["user_email"] == admin.email and item["material_name"] == "Auditado 2"
    assert item["before"]["name"] != item["after"]["name"]
    by_action = (await client.get("/api/audit", params={"material_id": material["id"], "action": "material.created"}, headers=h)).json()
    assert by_action["total"] == 1
    by_user = (await client.get("/api/audit", params={"user_id": str(admin.id), "entity_type": "material"}, headers=h)).json()
    assert by_user["total"] == 2
    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    assert (await client.get("/api/audit", params={"date_from": future}, headers=h)).json()["total"] == 0
    paged = (await client.get("/api/audit", params={"material_id": material["id"], "page_size": 1, "page": 2}, headers=h)).json()
    assert len(paged["items"]) == 1 and paged["items"][0]["action"] == "material.created" and paged["page"] == 2
    too_big = await client.get("/api/audit", params={"page_size": PARAMETER_DEFAULTS["audit"]["max_page_size"] + 1}, headers=h)
    assert too_big.status_code == 422 and too_big.json()["detail"]["code"] == "page_size_too_large"
    facets = (await client.get("/api/audit/facets", headers=h)).json()
    assert {"material.created", "material.updated", "auth.login"} <= set(facets["actions"])
    assert "material" in facets["entity_types"]


async def test_parameters_in_force(client, factory):
    admin = await factory.user(is_admin=True)
    token, _ = await login(client, admin)
    body = (await client.get("/api/parameters", headers=bearer(token))).json()
    assert {p["key"]: p["value"] for p in body} == PARAMETER_DEFAULTS
