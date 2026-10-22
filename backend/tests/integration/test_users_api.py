"""/api/users (admin): every operation, its audit row and its guards."""

import uuid

import pytest_asyncio
from sqlalchemy import select

from app.db.base import async_session_factory
from app.models import AuditLog
from helpers import TEST_PASSWORD, bearer, login


@pytest_asyncio.fixture
async def admin(client, factory):
    user = await factory.user(is_admin=True, name="Admin de prueba")
    token, _ = await login(client, user)
    return user, bearer(token)


async def _audit(entity_id: str) -> list[str]:
    async with async_session_factory() as session:
        return (await session.execute(select(AuditLog.action).where(AuditLog.entity_id == entity_id).order_by(AuditLog.created_at))).scalars().all()


async def _create(client, factory, h, email=None, **extra):
    email = email or f"nuevo-{uuid.uuid4().hex[:8]}@aal-test.es"
    res = await client.post("/api/users", json={"email": email, "display_name": "Nuevo", **extra}, headers=h)
    assert res.status_code == 201, res.text
    body = res.json()
    factory.user_ids.append(uuid.UUID(body["user"]["id"]))
    return body


async def test_create_gives_a_temporary_password_once_and_forces_a_change(client, factory, admin):
    admin_user, h = admin
    body = await _create(client, factory, h, email="Mayusculas@AAL-test.es")
    user = body["user"]
    assert user["email"] == "mayusculas@aal-test.es"
    assert user["must_change_password"] is True and user["is_admin"] is False
    assert len(body["temporary_password"]) == 16
    client.cookies.clear()
    token, _ = await login(client, user["email"], body["temporary_password"])
    assert (await client.get("/api/auth/me", headers=bearer(token))).json()["must_change_password"] is True
    assert await _audit(user["id"]) == ["user.created", "auth.login"]


async def test_create_refuses_a_taken_email_and_a_bad_one(client, factory, admin):
    _admin, h = admin
    existing = await factory.user()
    res = await client.post("/api/users", json={"email": existing.email, "display_name": "x"}, headers=h)
    assert res.status_code == 409 and res.json()["detail"]["code"] == "user_email_taken"
    res = await client.post("/api/users", json={"email": "no-es-un-email", "display_name": "x"}, headers=h)
    assert res.status_code == 422 and res.json()["detail"]["fields"][0]["field"] == "email"


async def test_list_and_search(client, factory, admin):
    _admin, h = admin
    target = await factory.user(name="Persona Buscable Zeta")
    material = await factory.material()
    await factory.assign(target, material, "revisor")
    found = (await client.get("/api/users", params={"q": "buscable"}, headers=h)).json()
    assert [u["id"] for u in found] == [str(target.id)]
    assert found[0]["materials"] == [{"material_id": str(material.id), "material_name": material.name, "role": "revisor"}]
    assert "password_hash" not in (await client.get("/api/users", headers=h)).text


async def test_edit_needs_the_current_version(client, factory, admin):
    _admin, h = admin
    target = await factory.user()
    res = await client.patch(f"/api/users/{target.id}", json={"version": 1, "display_name": "Renombrado"}, headers=h)
    assert res.status_code == 200 and res.json()["version"] == 2 and res.json()["display_name"] == "Renombrado"
    res = await client.patch(f"/api/users/{target.id}", json={"version": 1, "display_name": "Otra vez"}, headers=h)
    assert res.status_code == 409 and res.json()["detail"] == {"code": "version_conflict", "current_version": 2}
    assert await _audit(str(target.id)) == ["user.updated"]


async def test_deactivate_and_reactivate(client, factory, admin):
    _admin, h = admin
    target = await factory.user()
    res = await client.patch(f"/api/users/{target.id}", json={"version": 1, "is_active": False}, headers=h)
    assert res.json()["is_active"] is False
    res = await client.patch(f"/api/users/{target.id}", json={"version": 2, "is_active": True}, headers=h)
    assert res.json()["is_active"] is True
    client.cookies.clear()
    await login(client, target)
    assert await _audit(str(target.id)) == ["user.deactivated", "user.reactivated", "auth.login"]


async def test_reset_password(client, factory, admin):
    _admin, h = admin
    target = await factory.user()
    res = await client.post(f"/api/users/{target.id}/reset-password", headers=h)
    assert res.status_code == 200
    temporary = res.json()["temporary_password"]
    assert res.json()["user"]["must_change_password"] is True
    client.cookies.clear()
    assert (await client.post("/api/auth/login", json={"email": target.email, "password": TEST_PASSWORD})).status_code == 401
    await login(client, target, temporary)


async def test_soft_delete_needs_confirmation_and_keeps_the_row(client, factory, admin):
    _admin, h = admin
    target = await factory.user()
    res = await client.delete(f"/api/users/{target.id}", headers=h)
    assert res.status_code == 400 and res.json()["detail"]["code"] == "confirmation_required"
    assert (await client.delete(f"/api/users/{target.id}?confirm=true", headers=h)).status_code == 204
    listed = [u["id"] for u in (await client.get("/api/users", headers=h)).json()]
    assert str(target.id) not in listed
    deleted = [u for u in (await client.get("/api/users", params={"include_deleted": True}, headers=h)).json() if u["id"] == str(target.id)]
    assert deleted and deleted[0]["deleted_at"] is not None
    assert (await client.patch(f"/api/users/{target.id}", json={"version": 2, "display_name": "x"}, headers=h)).status_code == 404
    res = await client.post("/api/users", json={"email": target.email, "display_name": "x"}, headers=h)
    assert res.json()["detail"]["code"] == "user_email_deleted"


async def test_nobody_removes_their_own_access(client, admin):
    admin_user, h = admin
    for body in ({"version": 1, "is_admin": False}, {"version": 1, "is_active": False}):
        res = await client.patch(f"/api/users/{admin_user.id}", json=body, headers=h)
        assert res.status_code == 409 and res.json()["detail"]["code"] == "cannot_change_own_access"
    assert (await client.delete(f"/api/users/{admin_user.id}?confirm=true", headers=h)).json()["detail"]["code"] == "cannot_change_own_access"
    assert (await client.post(f"/api/users/{admin_user.id}/reset-password", headers=h)).status_code == 409
    # Renaming oneself is fine.
    assert (await client.patch(f"/api/users/{admin_user.id}", json={"version": 1, "display_name": "Yo"}, headers=h)).status_code == 200
