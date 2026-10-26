"""The CONFUNFIS (E13) with the whole demo loaded (catalog, materials,
articles and scripts/seed_demo_confunfis.py): the figures of the encargo
§2.3, the views (tree, functional, table, card), editing with its checks
and its version, "duplicar como alternativo" and "añadir CS alternativo",
the link with the article master, the extension points (copy, removing a
subcategory, catalog version impact, dónde se usa) and the permissions."""

import sys
from pathlib import Path

import pytest_asyncio
from sqlalchemy import delete, func, select

from app.db.base import async_session_factory
from app.models import Article, ArticleReference, Material, PhysicalPosition
from app.services import confunfis
from helpers import bearer, login
from integration.test_catalog import catalog, imported  # noqa: F401

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
TRAMONTANA, PUESTO = "VTL 4X4 TRAMONTANA", "VTL 4X4 TRAMONTANA PUESTO DE MANDO"


async def _wipe_articles():
    async with async_session_factory() as session:
        await session.execute(delete(Article))
        await session.commit()


@pytest_asyncio.fixture
async def demo(client, factory, catalog):  # noqa: F811
    sys.path.insert(0, str(SCRIPTS))
    import seed_demo_articles
    import seed_demo_confunfis
    import seed_demo_materials

    await _wipe_articles()
    admin_user = await factory.user(is_admin=True)
    admin = bearer((await login(client, admin_user))[0])
    await imported(client, admin)
    names = [m[0] for m in seed_demo_materials.DEMO_MATERIALS]
    try:
        await seed_demo_materials.seed()
        assert await seed_demo_articles.seed() == 0
        assert await seed_demo_confunfis.seed() == 0
        async with async_session_factory() as session:
            materials = {m.name: m for m in (await session.execute(select(Material).where(Material.name.in_(names)))).scalars()}
        people = {"admin": admin}
        for role in ("analista", "revisor", "observador"):
            user = await factory.user()
            await factory.assign(user, materials[TRAMONTANA], role)
            people[role] = bearer((await login(client, user))[0])
        outsider = await factory.user()
        await factory.assign(outsider, materials[PUESTO], "analista")
        people["outsider"] = bearer((await login(client, outsider))[0])
        yield {"people": people, "materials": materials, "seed": seed_demo_confunfis}
    finally:
        async with async_session_factory() as session:
            await session.execute(delete(Material).where(Material.name.in_(names) | Material.copied_from_material_id.is_not(None)))
            await session.commit()
        await _wipe_articles()


def base(demo, name=TRAMONTANA):
    return f"/api/materials/{demo['materials'][name].id}/confunfis"


async def all_rows(client, demo, headers, name=TRAMONTANA, **params):
    return (await client.get(f"{base(demo, name)}/rows", params={"page_size": 1000, **params}, headers=headers)).json()


def find(rows, sns, co="01", al="00"):
    return [r for r in rows if (r["sns"], r["co"], r["al"]) == (sns, co, al)]


async def test_the_figures_of_the_demo(client, demo):
    analyst = demo["people"]["analista"]
    summary = (await client.get(f"{base(demo)}/summary", headers=analyst)).json()
    assert (summary["rows"], summary["positions"]) == (46, 44)
    page = await all_rows(client, demo, analyst)
    rows = page["items"]
    assert page["total"] == 46 and len({r["sns"] for r in rows}) == 37
    assert (await all_rows(client, demo, demo["people"]["admin"], name=PUESTO))["total"] == 46

    by_code = {code: sorted(f"{r['sns']} {r['co']}" for r in rows if code in r["observation_codes"]) for code in confunfis.OBSERVATION_CODES}
    assert {k: v for k, v in by_code.items() if v} == {
        "OF-001": ["B35010 01"], "OF-002": ["B31010 01"], "OF-003": ["A24110 01"], "OF-004": ["B32020 01", "B32020 01"],
        "OF-007": ["A22140 02"], "OF-008": ["D53000 01"],
    }
    assert sum(r["ct_sigle"] == "S" for r in rows) == 8
    assert (await all_rows(client, demo, analyst, with_observations="true"))["total"] == 7
    assert sorted(r["sns"] for r in (await all_rows(client, demo, analyst, orphans="true"))["items"]) == ["A24110", "B31010"]

    totals = {r["sns"]: r["total"] for r in rows}
    assert {s: totals[s] for s in ("A21031", "A21030", "B33011", "D12000", "L41100")} == {"A21031": "18", "A21030": "6", "B33011": "4", "D12000": "2", "L41100": "1"}
    assert [r["total"] for r in rows if r["sns"] == "E19200"] == ["1", "1"]
    assert [r["cs_alternative"] for r in find(rows, "L41100")] == [True, True]
    assert all(r["alternative"] for r in find(rows, "A27010", "03", "01") + find(rows, "A27010", "03", "02"))

    # The tapón: no NOC nor P/N, linked by its name to the E12 provisional article.
    [tapon] = find(rows, "A22140", "02")
    assert tapon["article"]["nombre"] == "TAPÓN DE LLENADO DEPÓSITO" and tapon["article"]["noc"] is None and tapon["article"]["origin"] == "maestro"
    articles = {r["article"]["noc"] for r in rows if r["article"]["noc"]}
    async with async_session_factory() as session:
        refs = await session.scalar(select(func.count()).select_from(ArticleReference).where(ArticleReference.origin == "confunfis", ArticleReference.deleted_at.is_(None)))
        provisional = await session.scalar(select(func.count()).select_from(Article).where(Article.origin == "confunfis"))
    assert (len(articles), refs, provisional) == (41, 41, 0)

    # CUF montado: the radio (and the motor, whose NOC is also a demo material's CUF).
    admin_rows = (await all_rows(client, demo, demo["people"]["admin"]))["items"]
    mounted = {r["sns"]: r["mounted"]["name"] for r in admin_rows if r["mounted"]}
    assert mounted == {"E12300": "RADIO VHF RT-500", "A20000": "MOTOR DIESEL 6 CIL DM-6 280 CV"}
    # Without access to those materials: the badge, not which one.
    assert sorted(r["sns"] for r in rows if r["is_mounted"]) == ["A20000", "E12300"] and not any(r["mounted"] for r in rows)

    # "Dónde se usa" of the pistón: both CUF, A21030 01 00.
    piston = find(rows, "A21030")[0]["article"]["id"]
    used = (await client.get(f"/api/articles/{piston}", headers=demo["people"]["admin"])).json()["where_used"]
    assert sorted((u["material_name"], u["position"]) for u in used if u["kind"] == "confunfis_position") == [(TRAMONTANA, "A21030 01 00"), (PUESTO, "A21030 01 00")]
    # The analyst only opens the Tramontana.
    used = (await client.get(f"/api/articles/{piston}", headers=analyst)).json()["where_used"]
    assert [u["material_name"] for u in used if u["kind"] == "confunfis_position"] == [TRAMONTANA]


async def test_the_tree_the_functional_view_and_the_card(client, demo):
    observer = demo["people"]["observador"]
    root = (await client.get(f"{base(demo)}/tree", headers=observer)).json()
    assert root["root"]["sns"] == "000000" and root["parent"] == "000000 01 00"
    assert sorted(o["sns"] for o in root["orphans"]) == ["A24110", "B31010"] and root["cycles"] == []
    motor = next(r for r in root["items"] if r["sns"] == "A20000")
    piston = next(r for r in (await client.get(f"{base(demo)}/tree", params={"parent": "A20000 01 00"}, headers=observer)).json()["items"] if r["sns"] == "A21030")
    [rings] = (await client.get(f"{base(demo)}/tree", params={"parent": "A21030 01 00"}, headers=observer)).json()["items"]
    assert (motor["child_count"] > 0, piston["qty"], rings["qty"], rings["total"]) == (True, "6", "3", "18")
    # The computer under both cabinets.
    for al in ("01", "02"):
        level = (await client.get(f"{base(demo)}/tree", params={"parent": f"L48000 01 {al}"}, headers=observer)).json()
        assert [r["sns"] for r in level["items"]] == ["L41100"]

    card = (await client.get(f"{base(demo)}/rows/{rings['id']}", headers=observer)).json()
    assert card["chains"] == [[{"qty": "3", "sns": None}, {"qty": "6", "sns": "A21030"}, {"qty": "1", "sns": "A20000"}]]
    assert [p["sns"] for p in card["parents"]] == ["A21030"] and card["history"][0]["action"] == "confunfis.row_created"

    top = (await client.get(f"{base(demo)}/functional", headers=observer)).json()
    assert [r["sns"] for r in top["outside"]] == ["B35010"]
    # Every row in the configuration (all but B35010) under exactly one root.
    assert sum(n["rows_below"] for n in top["items"]) == 45


async def test_editing_with_its_checks(client, demo):
    analyst = demo["people"]["analista"]
    url = f"{base(demo)}/rows"
    for headers in (demo["people"]["revisor"], demo["people"]["observador"]):
        assert (await client.post(url, json={"sns": "A27010", "co": "04"}, headers=headers)).status_code == 403
    assert (await client.get(url, headers=demo["people"]["outsider"])).status_code == 404

    outside = await client.post(url, json={"sns": "B35010", "co": "02", "qty": 1}, headers=analyst)
    assert (outside.status_code, outside.json()["detail"]["problems"][0]["code"]) == (422, "sns_not_in_config")
    bad = await client.post(url, json={"sns": "A27010", "co": "4", "qty": "x"}, headers=analyst)
    assert {p["code"] for p in bad.json()["detail"]["problems"]} == {"two_digits", "qty_not_a_number"}

    slot = (await client.get(f"{base(demo)}/next-slot", params={"sns": "A27010"}, headers=analyst)).json()
    assert slot == {"co": "04", "al": "00"}
    res = await client.post(url, json={
        "sns": "A27010", "co": "04", "qty": 1, "article_name": "SOPORTE MOTOR TRASERO IZQUIERDO", "function_text": "Sujetar el motor",
        "cs_sns": "000000", "cs_co": "01", "cs_al": "00",
    }, headers=analyst)
    assert res.status_code == 201, res.text
    new = res.json()
    assert new["article"]["origin"] == "confunfis" and new["article"]["noc"] is None and new["observation_codes"] == ["OF-007"]

    dup = await client.post(f"{url}/{new['id']}/duplicate-alternative", json={"version": new["version"]}, headers=analyst)
    assert dup.status_code == 201, dup.text
    rows = (await all_rows(client, demo, analyst, sns="A27010"))["items"]
    assert sorted(r["al"] for r in rows if r["co"] == "04") == ["01", "02"]

    stale = await client.patch(f"{url}/{new['id']}", json={"version": new["version"], "qty": 2}, headers=analyst)
    assert stale.status_code == 409
    original = next(r for r in rows if r["co"] == "04" and r["al"] == "01")
    res = await client.patch(f"{url}/{original['id']}", json={"version": original["version"], "qty": "1.5"}, headers=analyst)
    assert res.status_code == 200 and "OF-006" in res.json()["observation_codes"]

    cs = await client.post(f"{url}/{original['id']}/alternative-cs", json={"version": res.json()["version"], "cs_sns": "A20000", "cs_co": "01", "cs_al": "00"}, headers=analyst)
    assert cs.status_code == 201 and cs.json()["cs_alternative"]

    # A seeded row outside the configuration can still get its QTY corrected.
    [chain] = find((await all_rows(client, demo, analyst))["items"], "B35010")
    assert (await client.patch(f"{url}/{chain['id']}", json={"version": chain["version"], "qty": 2}, headers=analyst)).status_code == 200

    for r in [x for x in (await all_rows(client, demo, analyst, sns="A27010"))["items"] if x["co"] == "04"]:
        assert (await client.delete(f"{url}/{r['id']}", params={"version": r["version"]}, headers=analyst)).status_code == 400
        assert (await client.delete(f"{url}/{r['id']}", params={"version": r["version"], "confirm": "true"}, headers=analyst)).status_code == 204
    assert (await all_rows(client, demo, analyst))["total"] == 46


async def test_the_duplicate_drops_its_observation_when_one_goes(client, demo):
    analyst = demo["people"]["analista"]
    first, second = find((await all_rows(client, demo, analyst))["items"], "B32020")
    await client.delete(f"{base(demo)}/rows/{second['id']}", params={"version": second["version"], "confirm": "true"}, headers=analyst)
    [left] = find((await all_rows(client, demo, analyst))["items"], "B32020")
    assert left["id"] == first["id"] and "OF-004" not in left["observation_codes"]


async def test_extension_points(client, demo):
    admin, analyst = demo["people"]["admin"], demo["people"]["analista"]
    tramontana = demo["materials"][TRAMONTANA]
    mid = tramontana.id
    current = (await client.get(f"/api/materials/{mid}/cuf", headers=analyst)).json()
    blocked = await client.put(f"/api/materials/{mid}/subcategories", json={"version": current["version"], "codes": ["0601", "0201"]}, headers=analyst)
    assert (blocked.status_code, blocked.json()["detail"]["code"]) == (409, "subcategory_used_by_confunfis")
    assert blocked.json()["detail"]["count"] == 1 and "C66100" in blocked.json()["detail"]["rows"]

    copy = await client.post(f"/api/materials/{mid}/copy", json={"name": "[test] copia", "noc": None, "copy_members": False}, headers=admin)
    assert copy.status_code == 201, copy.text
    copied = (await client.get(f"/api/materials/{copy.json()['id']}/confunfis/rows", params={"page_size": 1000}, headers=admin)).json()
    assert copied["total"] == 46 and {r["source"] for r in copied["items"]} == {"copia"}

    async with async_session_factory() as session:
        material = await session.get(Material, mid)
        extra = await confunfis._impact_rows(session, material, {"removed": ["C66100", "B35010"]})
    assert sorted(r["sns"] for r in extra["confunfis_rows"]) == ["B35010", "C66100"]


async def test_linking_with_the_article_master(client, demo):
    async with async_session_factory() as db:
        material = await db.get(Material, demo["materials"][TRAMONTANA].id)
        piston = (await db.execute(select(Article).where(Article.noc == "281533X900104"))).scalar_one()
        # By NOC, adding a second P/N of the same NOC (NT §9.1.6).
        link = await confunfis.link_article(db, noc="281533X900104", pn="DM6-1030-02", ncage="DEMO2", name=None, user_id=None, material=material)
        assert link.article.id == piston.id and not link.created and link.reference.pn == "DM6-1030-02" and not link.reference.principal
        # By P/N + NCAGE, without NOC.
        link = await confunfis.link_article(db, noc=None, pn="DM6-1030-02", ncage="DEMO2", name=None, user_id=None, material=material)
        assert link.article.id == piston.id
        # A P/N + NCAGE of another article stays out (OF-011).
        link = await confunfis.link_article(db, noc="281533X900103", pn="DM6-1030-02", ncage="DEMO2", name=None, user_id=None, material=material)
        assert link.reference is None and link.notes == [{"code": "OF-011", "params": {"pn": "DM6-1030-02", "ncage": "DEMO2"}}]
        # Nothing matches: a provisional one.
        link = await confunfis.link_article(db, noc=None, pn=None, ncage=None, name="PIEZA NUEVA", user_id=None, material=material)
        assert link.created and link.article.origin == "confunfis"
        await db.rollback()


async def test_the_seed_is_idempotent(client, demo):
    assert await demo["seed"].seed() == 0
    async with async_session_factory() as session:
        count = await session.scalar(select(func.count()).select_from(PhysicalPosition).where(PhysicalPosition.material_id == demo["materials"][TRAMONTANA].id))
    assert count == 46
