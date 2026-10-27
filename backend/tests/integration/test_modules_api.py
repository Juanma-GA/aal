"""/api/modules: the menu, the card, the admin's change."""

import pytest_asyncio
from sqlalchemy import select, update

from app.db.base import async_session_factory
from app.models import AuditLog, ModuleCatalog
from helpers import bearer, login


@pytest_asyncio.fixture
async def restore_fta():
    yield
    async with async_session_factory() as session:
        await session.execute(update(ModuleCatalog).where(ModuleCatalog.code == "fta").values(status="planificado", route=None))
        await session.commit()


async def test_menu_for_any_signed_in_user(client, factory):
    token, _ = await login(client, await factory.user())
    groups = (await client.get("/api/modules", headers=bearer(token))).json()
    assert [g["code"] for g in groups][:3] == ["inicio", "base", "paal"]
    assert sum(len(g["modules"]) for g in groups) == 46
    assert groups[0]["modules"][0]["code"] == "panel"
    assert (await client.get("/api/modules")).status_code == 401


async def test_card_with_requirements_dependencies_and_users(client, factory):
    token, _ = await login(client, await factory.user())
    card = (await client.get("/api/modules/confunfis", headers=bearer(token))).json()
    # E13 turned it on.
    assert card["group_name"] == "Base común" and (card["status"], card["route"]) == ("disponible", "/materiales/:materialId/confunfis")
    assert [r["rf_id"] for r in card["requirements"]] == ["RF-02"]
    assert [d["code"] for d in card["depends_on"]] == ["materiales", "articulos"]
    used_by = {u["code"] for u in card["used_by"]}
    assert {"tabla-partes", "validacion", "candidatos"} <= used_by
    assert card["deliverable"].startswith("Configuración funcional física")
    assert (await client.get("/api/modules/no-existe", headers=bearer(token))).json()["detail"]["code"] == "module_not_found"


async def test_only_the_admin_changes_a_module(client, factory, restore_fta):
    analyst = await factory.user()
    token, _ = await login(client, analyst)
    res = await client.patch("/api/modules/fta", json={"version": 1, "status": "en_desarrollo"}, headers=bearer(token))
    assert res.status_code == 403
    client.cookies.clear()
    admin_token, _ = await login(client, await factory.user(is_admin=True))
    h = bearer(admin_token)
    version = (await client.get("/api/modules/fta", headers=h)).json()["version"]
    res = await client.patch("/api/modules/fta", json={"version": version, "status": "en_desarrollo"}, headers=h)
    assert res.status_code == 200 and res.json()["status"] == "en_desarrollo" and res.json()["route"] is None
    stale = await client.patch("/api/modules/fta", json={"version": version, "status": "planificado"}, headers=h)
    assert stale.status_code == 409
    async with async_session_factory() as session:
        row = (await session.execute(select(AuditLog).where(AuditLog.entity_id == "fta").order_by(AuditLog.created_at.desc()))).scalars().first()
    assert row.action == "module.updated" and row.before["status"] == "planificado" and row.after["status"] == "en_desarrollo"


async def test_route_rules(client, factory, restore_fta):
    token, _ = await login(client, await factory.user(is_admin=True))
    h = bearer(token)
    v = (await client.get("/api/modules/fta", headers=h)).json()["version"]
    no_route = await client.patch("/api/modules/fta", json={"version": v, "status": "disponible"}, headers=h)
    assert no_route.json()["detail"]["code"] == "module_route_required"
    bad = await client.patch("/api/modules/fta", json={"version": v, "status": "disponible", "route": "https://otro.es"}, headers=h)
    assert bad.json()["detail"]["code"] == "module_route_invalid"
    ok = await client.patch("/api/modules/fta", json={"version": v, "status": "disponible", "route": "/materiales/:materialId/fta"}, headers=h)
    assert ok.json()["route"] == "/materiales/:materialId/fta"
    back = await client.patch("/api/modules/fta", json={"version": v + 1, "status": "planificado"}, headers=h)
    assert back.json()["route"] is None
    unknown = await client.patch("/api/modules/fta", json={"version": v + 2, "status": "hecho"}, headers=h)
    assert unknown.json()["detail"]["code"] == "module_status_unknown"
