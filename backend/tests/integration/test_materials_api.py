"""/api/materials and /api/materials/{id}/members."""

import uuid

import pytest_asyncio
from sqlalchemy import select

from app.db.base import async_session_factory
from app.models import AuditLog
from helpers import bearer, login


@pytest_asyncio.fixture
async def admin_h(client, factory):
    user = await factory.user(is_admin=True)
    token, _ = await login(client, user)
    return bearer(token)


async def _create(client, factory, h, **fields):
    body = {"name": f"CUF {uuid.uuid4().hex[:6]}", **fields}
    res = await client.post("/api/materials", json=body, headers=h)
    assert res.status_code == 201, res.text
    factory.material_ids.append(uuid.UUID(res.json()["id"]))
    return res.json()


async def test_create_get_edit_delete(client, factory, admin_h):
    created = await _create(client, factory, admin_h, noc="1234567890123", part_number="PN-1", ncage="ABC12", description="Vehículo")
    assert created["version"] == 1 and created["role"] is None and "material.editar" in created["permissions"]
    mid = created["id"]
    assert (await client.get(f"/api/materials/{mid}", headers=admin_h)).json()["noc"] == "1234567890123"
    res = await client.patch(f"/api/materials/{mid}", json={"version": 1, "name": "CUF renombrado", "ncage": None}, headers=admin_h)
    assert res.status_code == 200 and res.json()["name"] == "CUF renombrado" and res.json()["ncage"] is None and res.json()["version"] == 2
    res = await client.patch(f"/api/materials/{mid}", json={"version": 1, "name": "x"}, headers=admin_h)
    assert res.status_code == 409 and res.json()["detail"]["code"] == "version_conflict"
    assert (await client.delete(f"/api/materials/{mid}", headers=admin_h)).json()["detail"]["code"] == "confirmation_required"
    assert (await client.delete(f"/api/materials/{mid}?confirm=true", headers=admin_h)).status_code == 204
    assert (await client.get(f"/api/materials/{mid}", headers=admin_h)).status_code == 404
    async with async_session_factory() as session:
        actions = (await session.execute(select(AuditLog.action).where(AuditLog.entity_id == mid).order_by(AuditLog.created_at))).scalars().all()
    assert actions == ["material.created", "material.updated", "material.deleted"]


async def test_noc_and_ncage_formats_and_unique_noc(client, factory, admin_h):
    for bad in ({"noc": "123"}, {"noc": "12345678901234"}, {"ncage": "AB"}, {"noc": "abcdefghijklm"}, {"name": ""}):
        res = await client.post("/api/materials", json={"name": "x", **bad}, headers=admin_h)
        assert res.status_code == 422, bad
    await _create(client, factory, admin_h, noc="9999999999999")
    res = await client.post("/api/materials", json={"name": "otro", "noc": "9999999999999"}, headers=admin_h)
    assert res.status_code == 409 and res.json()["detail"]["code"] == "material_noc_taken"


async def test_members_assign_change_remove(client, factory, admin_h):
    material = await _create(client, factory, admin_h)
    user = await factory.user(name="Miembro")
    url = f"/api/materials/{material['id']}/members/{user.id}"
    res = await client.put(url, json={"role": "observador"}, headers=admin_h)
    assert res.status_code == 200 and res.json()["role"] == "observador"
    res = await client.put(url, json={"role": "revisor"}, headers=admin_h)
    assert res.json()["role"] == "revisor"
    members = (await client.get(f"/api/materials/{material['id']}/members", headers=admin_h)).json()
    assert [(m["email"], m["role"]) for m in members] == [(user.email, "revisor")]
    assert (await client.put(url, json={"role": "jefe"}, headers=admin_h)).json()["detail"]["code"] == "role_unknown"
    assert (await client.delete(url, headers=admin_h)).json()["detail"]["code"] == "confirmation_required"
    assert (await client.delete(f"{url}?confirm=true", headers=admin_h)).status_code == 204
    assert (await client.delete(f"{url}?confirm=true", headers=admin_h)).json()["detail"]["code"] == "member_not_found"
    async with async_session_factory() as session:
        rows = (
            await session.execute(
                select(AuditLog.action, AuditLog.before, AuditLog.after)
                .where(AuditLog.entity_id == f"{user.id}:{material['id']}")
                .order_by(AuditLog.created_at)
            )
        ).all()
    assert [r[0] for r in rows] == ["material_role.assigned", "material_role.changed", "material_role.removed"]
    assert rows[1][1] == {"user": user.email, "role": "observador"} and rows[1][2] == {"user": user.email, "role": "revisor"}


async def test_members_of_unknown_user_or_material(client, factory, admin_h):
    material = await _create(client, factory, admin_h)
    assert (await client.put(f"/api/materials/{material['id']}/members/{uuid.uuid4()}", json={"role": "analista"}, headers=admin_h)).json()["detail"]["code"] == "user_not_found"
    assert (await client.get(f"/api/materials/{uuid.uuid4()}/members", headers=admin_h)).json()["detail"]["code"] == "material_not_found"
