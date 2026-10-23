"""Materials / CUF (E11) through the API, with demo/CONF_FUN_DEMO.xlsx
imported: the normalized configuration (union without duplicates, with the
subcategory of origin), subcategories limited to the CUF's version, the
impact of changing the version, the copy, the requests for a new SNS, the
permissions, and seed_demo_materials with and without a catalog."""

import io
import sys
from pathlib import Path

import openpyxl
import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select

from app.db.base import async_session_factory
from app.models import AuditLog, Material, SnsRequest
from app.services import cuf
from helpers import bearer, login
from integration.test_catalog import DEMO, XLSX, analyse, catalog, imported  # noqa: F401

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


@pytest_asyncio.fixture
async def team(client, factory, catalog):  # noqa: F811
    """The demo catalog imported; the admin, an analyst and an observer of
    a material created by the admin."""
    admin_user = await factory.user(is_admin=True)
    admin = bearer((await login(client, admin_user))[0])
    await imported(client, admin)
    created = (await client.post("/api/materials", json={"name": "CUF de prueba E11"}, headers=admin)).json()
    material = await _material(created["id"])
    factory.material_ids.append(material.id)
    analyst_user, observer_user = await factory.user(), await factory.user()
    await factory.assign(analyst_user, material, "analista")
    await factory.assign(observer_user, material, "observador")
    analyst = bearer((await login(client, analyst_user))[0])
    observer = bearer((await login(client, observer_user))[0])
    yield {"admin": admin, "analyst": analyst, "observer": observer, "id": created["id"]}
    async with async_session_factory() as session:
        await session.execute(delete(SnsRequest))
        await session.execute(delete(Material).where(Material.copied_from_material_id.is_not(None)))
        await session.commit()


async def _material(material_id):
    async with async_session_factory() as session:
        return await session.get(Material, material_id)


async def put_subs(client, headers, material_id, codes):
    current = (await client.get(f"/api/materials/{material_id}/cuf", headers=headers)).json()
    return await client.put(f"/api/materials/{material_id}/subcategories", json={"version": current["version"], "codes": codes}, headers=headers)


@pytest.mark.parametrize("codes, total", [(["0601", "0201", "0102"], 65), (["0201"], 15), (["0601"], 48), (["0602"], 30), (["0601", "0201"], 62)])
async def test_the_union_of_the_subcategories(client, team, codes, total):
    res = await put_subs(client, team["analyst"], team["id"], codes)
    assert res.status_code == 200, res.text
    out = res.json()
    assert out["sns_count"] == total and sum(out["levels"].values()) == total
    assert [s["code"] for s in out["subcategories"]] == sorted(codes)


async def test_origins_tree_search_and_export(client, team):
    mid = team["id"]
    await put_subs(client, team["analyst"], mid, ["0601", "0201", "0102"])
    out = (await client.get(f"/api/materials/{mid}/cuf", headers=team["observer"])).json()
    assert {s["code"]: s["sns_count"] for s in out["subcategories"]} == {"0102": 4, "0201": 15, "0601": 48}
    roots = (await client.get(f"/api/materials/{mid}/normalized-config/tree", headers=team["observer"])).json()
    general = next(r for r in roots if r["sns"] == "000000")
    assert general["origins"] == ["0102", "0201", "0601"]  # once, from the three
    motor = (await client.get(f"/api/materials/{mid}/normalized-config/tree", params={"parent": "A21000"}, headers=team["observer"])).json()
    assert {n["sns"]: n["origins"] for n in motor}["A21030"] == ["0601"]
    found = (await client.get(f"/api/materials/{mid}/normalized-config/search", params={"q": "E12300"}, headers=team["observer"])).json()
    assert [(i["sns"], i["origins"]) for i in found["items"]] == [("E12300", ["0201"])]
    assert (await client.get(f"/api/materials/{mid}/normalized-config/search", params={"q": "B35010"}, headers=team["observer"])).json()["total"] == 0
    export = await client.get(f"/api/materials/{mid}/normalized-config/export", headers=team["observer"])
    rows = list(openpyxl.load_workbook(io.BytesIO(export.content))["CONF_FUN"].iter_rows(min_row=2, values_only=True))
    # The file rows of the three (0601 has 50: two repeat an SNS, CN-001).
    assert len(rows) == 69 and {f"{r[0]}{r[2]}" for r in rows} == {"0601", "0201", "0102"}


async def test_a_tracked_vehicle_has_its_own(client, team):
    await put_subs(client, team["analyst"], team["id"], ["0602"])
    tree = (await client.get(f"/api/materials/{team['id']}/normalized-config/search", params={"q": "A21030"}, headers=team["analyst"])).json()
    assert tree["items"][0]["origins"] == ["0602"]
    assert (await client.get(f"/api/materials/{team['id']}/normalized-config/search", params={"q": "B35010"}, headers=team["analyst"])).json()["total"] == 1


async def test_subcategories_are_limited_to_the_version_and_audited(client, team):
    res = await put_subs(client, team["analyst"], team["id"], ["0601", "0603"])
    assert (res.status_code, res.json()["detail"]) == (422, {"code": "subcategory_not_in_version", "codes": "0603"})
    # A code that is not a subcategory code never reaches the answer.
    bad = await put_subs(client, team["analyst"], team["id"], ["06O1<script>"])
    assert bad.status_code == 422 and "06O1" not in bad.text
    await put_subs(client, team["analyst"], team["id"], ["0601"])
    stale = await client.put(f"/api/materials/{team['id']}/subcategories", json={"version": 1, "codes": []}, headers=team["analyst"])
    assert stale.json()["detail"]["code"] == "version_conflict"
    async with async_session_factory() as session:
        row = (await session.execute(select(AuditLog).where(AuditLog.entity_id == team["id"], AuditLog.action == "material.subcategories_changed"))).scalar_one()
    assert row.after["added"] == ["0601"]


async def test_permissions(client, team):
    assert (await put_subs(client, team["observer"], team["id"], ["0601"])).status_code == 403
    assert (await client.get(f"/api/materials/{team['id']}/normalized-config/tree", headers=team["observer"])).status_code == 200
    copy = await client.post(f"/api/materials/{team['id']}/copy", json={"name": "Copia"}, headers=team["analyst"])
    assert copy.status_code == 403
    impact = await client.get(f"/api/materials/{team['id']}/catalog-version-impact", params={"to": team["id"]}, headers=team["analyst"])
    assert impact.status_code == 403


async def test_a_removal_guard_can_stop_it(client, team):
    """The extension point for E13: a CONFUNFIS that uses the SNS of a
    subcategory will stop its removal."""
    await put_subs(client, team["analyst"], team["id"], ["0601", "0201"])

    async def in_use(db, material, removed):
        return ("subcategory_in_use", {"codes": ", ".join(sorted(removed))}) if "0201" in removed else None

    cuf.SUBCATEGORY_REMOVAL_GUARDS.append(in_use)
    try:
        res = await put_subs(client, team["analyst"], team["id"], ["0601"])
        assert (res.status_code, res.json()["detail"]) == (409, {"code": "subcategory_in_use", "codes": "0201"})
        assert (await put_subs(client, team["analyst"], team["id"], ["0601", "0201", "0102"])).status_code == 200
    finally:
        cuf.SUBCATEGORY_REMOVAL_GUARDS.remove(in_use)


async def test_changing_the_catalog_version_shows_the_impact(client, team):
    mid = team["id"]
    await put_subs(client, team["analyst"], mid, ["0601", "0102"])
    first = (await client.get(f"/api/materials/{mid}/cuf", headers=team["admin"])).json()
    # A second version without E12300 nor the subcategory 0102.
    wb = openpyxl.load_workbook(io.BytesIO(DEMO.read_bytes()))
    ws = wb["CONF_FUN"]
    for r in sorted((r for r in range(2, ws.max_row + 1) if ws[f"F{r}"].value == "A21031" or ws[f"C{r}"].value == "02" and ws[f"A{r}"].value == "01"), reverse=True):
        ws.delete_rows(r, 1)
    out = io.BytesIO()
    wb.save(out)
    job = await analyse(client, team["admin"], out.getvalue())
    assert (await client.post(f"/api/import-jobs/{job['id']}/apply", headers=team["admin"])).status_code == 200
    second = (await client.get("/api/catalog/versions", headers=team["admin"])).json()[0]
    impact = (await client.get(f"/api/materials/{mid}/catalog-version-impact", params={"to": second["id"]}, headers=team["admin"])).json()
    assert impact["subcategories_missing"] == ["0102"] and "A21031" in impact["removed"] and impact["added"] == []
    assert (impact["sns_before"], impact["sns_after"]) == (51, 47)
    body = {"version": first["version"], "catalog_version_id": second["id"], "confirm": False}
    assert (await client.put(f"/api/materials/{mid}/catalog-version", json=body, headers=team["admin"])).json()["detail"]["code"] == "confirmation_required"
    done = (await client.put(f"/api/materials/{mid}/catalog-version", json={**body, "confirm": True}, headers=team["admin"])).json()
    assert (done["catalog_version"]["number"], [s["code"] for s in done["subcategories"]], done["sns_count"]) == (2, ["0601"], 47)
    # A new CUF gets the active version.
    new = (await client.post("/api/materials", json={"name": "CUF nuevo E11"}, headers=team["admin"])).json()
    async with async_session_factory() as session:
        assert (await session.get(Material, new["id"])).catalog_version_id is not None
        await session.execute(delete(Material).where(Material.id == new["id"]))
        await session.commit()
    assert new["catalog_version_id"] == second["id"]


async def test_copy_is_independent_and_keeps_its_origin(client, team):
    mid = team["id"]
    await put_subs(client, team["analyst"], mid, ["0601", "0201"])
    body = {"name": "Variante E11", "noc": "232033x900099", "ncage": "demo9", "copy_members": True}
    copy = await client.post(f"/api/materials/{mid}/copy", json=body, headers=team["admin"])
    assert copy.status_code == 201, copy.text
    variant = copy.json()
    assert (variant["noc"], variant["ncage"], variant["copied_from_material_id"]) == ("232033X900099", "DEMO9", mid)
    v_cuf = (await client.get(f"/api/materials/{variant['id']}/cuf", headers=team["admin"])).json()
    assert [s["code"] for s in v_cuf["subcategories"]] == ["0201", "0601"] and v_cuf["copied_from"]["id"] == mid
    team_of_copy = (await client.get(f"/api/materials/{variant['id']}/members", headers=team["admin"])).json()
    assert sorted(m["role"] for m in team_of_copy) == ["analista", "observador"]
    # Independent: a change to the copy does not touch the original.
    await put_subs(client, team["admin"], variant["id"], ["0602"])
    original = (await client.get(f"/api/materials/{mid}/cuf", headers=team["admin"])).json()
    assert [s["code"] for s in original["subcategories"]] == ["0201", "0601"]
    assert [v["name"] for v in original["variants"]] == ["Variante E11"]
    async with async_session_factory() as session:
        row = (await session.execute(select(AuditLog).where(AuditLog.entity_id == variant["id"], AuditLog.action == "material.copied"))).scalar_one()
    assert sorted(m["role"] for m in row.after["members"]) == ["analista", "observador"]
    taken = await client.post(f"/api/materials/{mid}/copy", json={"name": "Otra", "noc": "232033X900099"}, headers=team["admin"])
    assert taken.json()["detail"]["code"] == "material_noc_taken"


async def test_sns_requests(client, team):
    base = f"/api/materials/{team['id']}/sns-requests"
    body = {"name": "Sistema de vigilancia perimetral", "parent_sns": "e10000", "justification": "No existe en la configuración normalizada."}
    assert (await client.post(base, json=body, headers=team["observer"])).status_code == 403
    created = (await client.post(base, json=body, headers=team["analyst"])).json()
    assert (created["state"], created["parent_sns"]) == ("borrador", "E10000")
    assert (await client.post(base, json={**body, "justification": ""}, headers=team["analyst"])).status_code == 422
    edited = (await client.patch(f"{base}/{created['id']}", json={**body, "function": "Vigila", "version": 1}, headers=team["analyst"])).json()
    sent = (await client.post(f"{base}/{created['id']}/submit", json={"version": edited["version"]}, headers=team["analyst"])).json()
    assert sent["state"] == "enviada" and sent["sent_at"]
    late = await client.patch(f"{base}/{created['id']}", json={**body, "version": sent["version"]}, headers=team["analyst"])
    assert (late.status_code, late.json()["detail"]["code"]) == (409, "sns_request_wrong_state")
    export = await client.get(f"{base}/export", headers=team["observer"])
    rows = list(openpyxl.load_workbook(io.BytesIO(export.content))["SOLICITUDES SNS"].iter_rows(min_row=2, values_only=True))
    assert [(r[4], r[3]) for r in rows] == [("Sistema de vigilancia perimetral", "E10000")]
    resolve = {"version": sent["version"], "decision": "rechazada", "response": "Ya cubierto por E19000."}
    assert (await client.post(f"{base}/{created['id']}/resolve", json=resolve, headers=team["analyst"])).status_code == 403
    done = (await client.post(f"{base}/{created['id']}/resolve", json=resolve, headers=team["admin"])).json()
    assert (done["state"], done["response"], done["resolved_by"] is not None) == ("rechazada", "Ya cubierto por E19000.", True)
    draft = (await client.post(base, json=body, headers=team["analyst"])).json()
    assert (await client.delete(f"{base}/{draft['id']}", params={"version": 1}, headers=team["analyst"])).json()["detail"]["code"] == "confirmation_required"
    assert (await client.delete(f"{base}/{draft['id']}", params={"version": 1, "confirm": "true"}, headers=team["analyst"])).status_code == 204
    assert [r["id"] for r in (await client.get(base, headers=team["observer"])).json()] == [created["id"]]
    async with async_session_factory() as session:
        actions = (await session.execute(select(AuditLog.action).where(AuditLog.entity_id == created["id"]).order_by(AuditLog.created_at))).scalars().all()
    assert actions == ["sns_request.created", "sns_request.updated", "sns_request.sent", "sns_request.rejected"]
    # Nobody resolves a request of a deleted material.
    other = (await client.post(base, json=body, headers=team["analyst"])).json()
    other = (await client.post(f"{base}/{other['id']}/submit", json={"version": 1}, headers=team["analyst"])).json()
    assert (await client.delete(f"/api/materials/{team['id']}", params={"confirm": "true"}, headers=team["admin"])).status_code == 204
    late = await client.post(f"{base}/{other['id']}/resolve", json={**resolve, "version": other["version"]}, headers=team["admin"])
    assert late.status_code == 404


async def test_seed_demo_materials_with_and_without_a_catalog(client, factory, catalog):  # noqa: F811
    sys.path.insert(0, str(SCRIPTS))
    import seed_demo_materials as seed

    names = [m[0] for m in seed.DEMO_MATERIALS]

    async def demo():
        async with async_session_factory() as session:
            rows = (await session.execute(select(Material).where(Material.name.in_(names), Material.deleted_at.is_(None)))).scalars().all()
            return {m.name: (m, await cuf.subcategory_codes(session, m.id)) for m in rows}

    try:
        await seed.seed()  # no catalog
        first = await demo()
        assert len(first) == 5 and all(codes == [] for _m, codes in first.values())
        pm, tramontana = first["VTL 4X4 TRAMONTANA PUESTO DE MANDO"][0], first["VTL 4X4 TRAMONTANA"][0]
        assert pm.copied_from_material_id == tramontana.id
        admin = bearer((await login(client, await factory.user(is_admin=True)))[0])
        await imported(client, admin)
        await seed.seed()
        await seed.seed()  # idempotent
        second = await demo()
        assert len(second) == 5
        assert {name: codes for name, (_m, codes) in second.items()} == {
            "VTL 4X4 TRAMONTANA": ["0102", "0201", "0601"],
            "VTL 4X4 TRAMONTANA PUESTO DE MANDO": ["0102", "0201", "0601"],
            "RADIO VHF RT-500": ["0201"],
            "MOTOR DIESEL 6 CIL DM-6 280 CV": ["0601"],
            "VTO GREGAL": ["0602"],
        }
        async with async_session_factory() as session:
            counts = {name: len(await cuf.normalized_config(session, m)) for name, (m, _c) in second.items()}
        assert counts == {
            "VTL 4X4 TRAMONTANA": 65, "VTL 4X4 TRAMONTANA PUESTO DE MANDO": 65, "RADIO VHF RT-500": 15,
            "MOTOR DIESEL 6 CIL DM-6 280 CV": 48, "VTO GREGAL": 30,
        }
    finally:
        async with async_session_factory() as session:
            await session.execute(delete(Material).where(Material.name.in_(names)))
            await session.commit()
        assert await _count_named(names) == 0


async def _count_named(names):
    async with async_session_factory() as session:
        return await session.scalar(select(func.count()).select_from(Material).where(Material.name.in_(names)))
