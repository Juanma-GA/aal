"""E12 flecos 1, 2 and 4: deleting a catalog version (logical, never the
active one nor one a CUF uses), activating an older one, annulling a sent
SNS request (admin, with a reason; out of the list and the export, in the
audit, back with "Mostrar anuladas"), the author discarding their draft,
and the sidebar preferences."""

from sqlalchemy import select

from app.db.base import async_session_factory
from app.models import AuditLog
from helpers import bearer, login
from integration.test_catalog import DEMO, edited, imported
from integration.test_cuf import catalog, team  # noqa: F401


async def _versions(client, headers):
    return (await client.get("/api/catalog/versions", headers=headers)).json()


async def test_deleting_a_catalog_version(client, team):  # noqa: F811
    admin, mid = team["admin"], team["id"]
    [v1] = await _versions(client, admin)
    _, v2 = await imported(client, admin, edited(DEMO.read_bytes(), "G6", "CIGÜEÑAL FORJADO"))
    active = await client.delete(f"/api/catalog/versions/{v2['id']}", params={"version": v2["version"], "confirm": "true"}, headers=admin)
    assert (active.status_code, active.json()["detail"]["code"]) == (409, "catalog_version_active")
    in_use = await client.delete(f"/api/catalog/versions/{v1['id']}", params={"version": 2, "confirm": "true"}, headers=admin)
    assert (in_use.status_code, in_use.json()["detail"]) == (409, {**in_use.json()["detail"], "code": "catalog_version_in_use", "materials": "CUF de prueba E11"})
    assert (await client.delete(f"/api/catalog/versions/{v1['id']}", params={"version": 2}, headers=admin)).json()["detail"]["code"] == "confirmation_required"
    assert (await client.delete(f"/api/catalog/versions/{v1['id']}", params={"version": 2, "confirm": "true"}, headers=team["analyst"])).status_code == 403
    # The CUF moves to v2 ("Cambiar versión", E11): v1 can go, and no CUF moves to it again.
    cuf = (await client.get(f"/api/materials/{mid}/cuf", headers=admin)).json()
    moved = await client.put(f"/api/materials/{mid}/catalog-version", json={"version": cuf["version"], "catalog_version_id": v2["id"], "confirm": True}, headers=admin)
    assert moved.status_code == 200, moved.text
    stale = await client.delete(f"/api/catalog/versions/{v1['id']}", params={"version": 1, "confirm": "true"}, headers=admin)
    assert stale.json()["detail"]["code"] == "version_conflict"
    v1_now = next(v for v in await _versions(client, admin) if v["id"] == v1["id"])
    ok = await client.delete(f"/api/catalog/versions/{v1['id']}", params={"version": v1_now["version"], "confirm": "true"}, headers=admin)
    assert ok.status_code == 204
    assert [v["number"] for v in await _versions(client, admin)] == [2]
    cuf = (await client.get(f"/api/materials/{mid}/cuf", headers=admin)).json()
    back = await client.put(f"/api/materials/{mid}/catalog-version", json={"version": cuf["version"], "catalog_version_id": v1["id"], "confirm": True}, headers=admin)
    assert back.json()["detail"]["code"] == "catalog_version_not_found"
    assert (await client.get(f"/api/materials/{mid}/catalog-version-impact", params={"to": v1["id"]}, headers=admin)).status_code == 404
    diff = await client.get("/api/catalog/diff", params={"from_version": v1["id"], "to_version": v2["id"]}, headers=admin)
    assert diff.json()["detail"]["code"] == "catalog_version_not_found"
    async with async_session_factory() as session:
        row = (await session.execute(select(AuditLog).where(AuditLog.entity_id == v1["id"], AuditLog.action == "catalog_version.deleted"))).scalar_one()
    assert (row.before["deleted"], row.after["deleted"], row.after["number"]) == (False, True, 1)


async def test_activating_an_older_version(client, team):  # noqa: F811
    admin = team["admin"]
    [v1] = await _versions(client, admin)
    _, v2 = await imported(client, admin, edited(DEMO.read_bytes(), "G6", "CIGÜEÑAL FORJADO"))
    v1_now = next(v for v in await _versions(client, admin) if v["id"] == v1["id"])
    assert (await client.post(f"/api/catalog/versions/{v1['id']}/activate", json={"version": v1_now["version"], "confirm": True}, headers=team["analyst"])).status_code == 403
    res = await client.post(f"/api/catalog/versions/{v1['id']}/activate", json={"version": v1_now["version"], "confirm": True}, headers=admin)
    assert res.status_code == 200 and res.json()["is_active"]
    assert [(v["number"], v["is_active"]) for v in await _versions(client, admin)] == [(2, False), (1, True)]
    # The one that is no longer active can be deleted (no CUF uses it).
    v2_now = next(v for v in await _versions(client, admin) if v["id"] == v2["id"])
    assert (await client.delete(f"/api/catalog/versions/{v2['id']}", params={"version": v2_now["version"], "confirm": "true"}, headers=admin)).status_code == 204
    async with async_session_factory() as session:
        actions = (await session.execute(select(AuditLog.action).where(AuditLog.entity_id == v1["id"]).order_by(AuditLog.created_at))).scalars().all()
    assert actions[-1] == "catalog_version.activated"


async def test_annulling_and_discarding_sns_requests(client, factory, team):  # noqa: F811
    base = f"/api/materials/{team['id']}/sns-requests"
    body = {"name": "Sistema de vigilancia perimetral", "justification": "No está en la configuración normalizada."}
    sent = (await client.post(base, json=body, headers=team["analyst"])).json()
    sent = (await client.post(f"{base}/{sent['id']}/submit", json={"version": 1}, headers=team["analyst"])).json()
    # A sent request is not discarded: it is annulled, by an admin, with a reason.
    assert (await client.delete(f"{base}/{sent['id']}", params={"version": sent["version"], "confirm": "true"}, headers=team["analyst"])).status_code == 409
    annul = f"{base}/{sent['id']}/annul"
    assert (await client.post(annul, json={"version": sent["version"], "reason": "Duplicada"}, headers=team["analyst"])).status_code == 403
    assert (await client.post(annul, json={"version": sent["version"], "reason": "  "}, headers=team["admin"])).status_code == 422
    assert (await client.post(annul, json={"version": sent["version"], "reason": "Duplicada de la 12"}, headers=team["admin"])).status_code == 204
    assert (await client.get(base, headers=team["admin"])).json() == []
    assert (await client.get(base, params={"annulled": "true"}, headers=team["analyst"])).status_code == 403
    [shown] = (await client.get(base, params={"annulled": "true"}, headers=team["admin"])).json()
    assert (shown["id"], shown["annul_reason"], shown["annulled_by"] is not None) == (sent["id"], "Duplicada de la 12", True)
    export = await client.get(f"{base}/export", headers=team["admin"])
    assert export.status_code == 200
    import io

    import openpyxl

    assert list(openpyxl.load_workbook(io.BytesIO(export.content))["SOLICITUDES SNS"].iter_rows(min_row=2, values_only=True)) == []
    async with async_session_factory() as session:
        row = (await session.execute(select(AuditLog).where(AuditLog.entity_id == sent["id"], AuditLog.action == "sns_request.annulled"))).scalar_one()
    assert (row.before["state"], row.after["annul_reason"]) == ("enviada", "Duplicada de la 12")
    # A draft: its author discards it, even without material.editar now; nobody else without it.
    draft = (await client.post(base, json=body, headers=team["analyst"])).json()
    assert (await client.delete(f"{base}/{draft['id']}", params={"version": 1, "confirm": "true"}, headers=team["observer"])).status_code == 403
    assert (await client.delete(f"{base}/{draft['id']}", params={"version": 1, "confirm": "true"}, headers=team["analyst"])).status_code == 204
    # Discarded drafts never come back, not even with "Mostrar anuladas".
    assert [r["id"] for r in (await client.get(base, params={"annulled": "true"}, headers=team["admin"])).json()] == [sent["id"]]


async def test_sidebar_preferences(client, factory):
    user = await factory.user()
    h = bearer((await login(client, user))[0])
    limits = (await client.get("/api/me/ui-settings", headers=h)).json()["sidebar_width"]
    assert limits == {"min": 200, "max": 480, "default": 256}
    res = await client.put("/api/me/ui-preferences", json={"sidebar_width": 320, "sidebar_folded": True, "sidebar_side": "right"}, headers=h)
    prefs = res.json()["ui_preferences"]
    assert (prefs["sidebar_width"], prefs["sidebar_folded"], prefs["sidebar_side"]) == (320, True, "right")
    too_wide = await client.put("/api/me/ui-preferences", json={"sidebar_width": 2000}, headers=h)
    assert (too_wide.status_code, too_wide.json()["detail"]["code"]) == (422, "sidebar_width_out_of_range")
    assert (await client.put("/api/me/ui-preferences", json={"sidebar_side": "top"}, headers=h)).status_code == 422
    # Kept across sessions: a new login sees them.
    again = bearer((await login(client, user))[0])
    assert (await client.get("/api/auth/me", headers=again)).json()["ui_preferences"]["sidebar_width"] == 320


async def test_the_detail_panel_width(client, factory):
    """E15: the docked panel's width, kept per user within the "ui" parameter."""
    user = await factory.user()
    h = bearer((await login(client, user))[0])
    limits = (await client.get("/api/me/ui-settings", headers=h)).json()["detail_panel_width"]
    assert limits == {"min": 320, "max": 960, "default": 480}
    saved = await client.put("/api/me/ui-preferences", json={"detail_panel_width": 600}, headers=h)
    assert saved.json()["ui_preferences"]["detail_panel_width"] == 600
    too_narrow = await client.put("/api/me/ui-preferences", json={"detail_panel_width": 100}, headers=h)
    assert (too_narrow.status_code, too_narrow.json()["detail"]["code"]) == (422, "detail_panel_width_out_of_range")
