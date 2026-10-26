"""The rest of RF-02 (E14) with the whole demo loaded: the parts table of an
article, the functional products, the extra functions and the
incompatibilities of a CUF -- the figures of the encargo §2.3, every new
observation, the rules, the copy remapped onto the new rows, removing a
row with what hangs from it, the guards and the permissions."""

from sqlalchemy import func, select

from app.db.base import async_session_factory
from app.models import Article, ArticlePart, AuditLog, ExtraFunction, FunctionalProduct, Incompatibility, Material, PhysicalPosition
from app.services import confunfis, cuf
from app.services import confunfis_extras as extras
from integration.test_catalog import catalog  # noqa: F401
from integration.test_confunfis import PUESTO, TRAMONTANA, all_rows, base, demo, find  # noqa: F401

PUMP, GASKET, PISTON = "432033X900201", "533033X900202", "281533X900104"


async def _article(noc):
    async with async_session_factory() as session:
        return (await session.execute(select(Article).where(Article.noc == noc, Article.deleted_at.is_(None)))).scalar_one()


def parts_url(article):
    return f"/api/articles/{article.id}/parts"


async def test_the_figures_of_the_demo(client, demo):
    analyst, admin = demo["people"]["analista"], demo["people"]["admin"]
    pump = await _article(PUMP)
    parts = (await client.get(parts_url(pump), headers=analyst)).json()
    assert [(p["cop"], p["alp"], p["article"]["noc"], p["article"]["pn"], p["quantity"]) for p in parts] == [
        ("01", "00", "533033X900202", "DM6-2110-11", "1"), ("02", "01", "473033X900203", "DM6-2110-21", "1"), ("02", "02", "473033X900204", "RC-4471-B", "1"),
    ]
    assert [p["alternative"] for p in parts] == [False, True, True] and all(not p["observation_codes"] for p in parts)

    # The CUF's "Tabla de partes": the gasket 1, the racor 1 (its two ALP once each).
    cuf_parts = (await client.get(f"{base(demo)}/parts", headers=analyst)).json()
    assert [(p["parent"]["nombre"], p["cop"], p["alp"], p["total"], p["parent_positions"]) for p in cuf_parts] == [
        ("BOMBA DE AGUA DM-6", "01", "00", "1", ["A22110 01 00"]), ("BOMBA DE AGUA DM-6", "02", "01", "1", ["A22110 01 00"]),
        ("BOMBA DE AGUA DM-6", "02", "02", "1", ["A22110 01 00"]),
    ]
    gasket = await _article(GASKET)
    used = (await client.get(f"/api/articles/{gasket.id}", headers=analyst)).json()["where_used"]
    assert [(u["article_name"], u["cop"], u["alp"]) for u in used if u["kind"] == "part_of"] == [("BOMBA DE AGUA DM-6", "01", "00")]

    for name, who in ((TRAMONTANA, analyst), (PUESTO, admin)):
        products = (await client.get(f"{base(demo, name)}/products", headers=who)).json()
        assert len(products) == 8 and len({p["pol_code"] for p in products}) == 7
        assert sorted(p["nae"] for p in products if p["pol_code"] == "O-1236") == ["E", "N"]
        assert [(p["supply_unit"], p["observation_codes"]) for p in products if p["observation_codes"]] == [("ZZ", ["OPF-004"])]
        assert all(p["pol_description"] == p["designation"] for p in products)

        rows = (await all_rows(client, demo, who, name=name))["items"]
        ids = {r["id"] for r in rows}
        [extra] = (await client.get(f"{base(demo, name)}/extra-functions", headers=who)).json()
        assert (extra["row"]["position"], extra["row"]["name"], extra["sns"], extra["sns_name"], extra["criterion"], extra["comment"]) == (
            "E12300 01 00", "RADIO VHF RT-500", "E19200", "SWITCHES", "funcion_principal", "conmutador de datos integrado",
        )
        [item] = (await client.get(f"{base(demo, name)}/incompatibilities", headers=who)).json()
        assert (item["row_a"]["position"], item["row_a"]["name"], item["kind"], item["row_b"]["position"], item["row_b"]["name"], item["reason"]) == (
            "L41120 01 00", "SOFTWARE DE MISIÓN V2.1", "requiere", "L41130 01 00", "FIRMWARE ORDENADOR V1.4", "compatibilidad SW/FW",
        )
        # On the material's own rows.
        assert {extra["row"]["id"], item["row_a"]["id"], item["row_b"]["id"]} <= ids
        [radio] = find(rows, "E12300")
        assert (radio["extra_function_count"], find(rows, "L41120")[0]["incompatibility_count"], find(rows, "L41130")[0]["incompatibility_count"]) == (1, 1, 1)
        summary = (await client.get(f"{base(demo, name)}/summary", headers=who)).json()
        assert (summary["products"], summary["multifunction_rows"], summary["incompatibility_rows"]) == (8, 1, 2)
    tramontana_extra = (await client.get(f"{base(demo)}/extra-functions", headers=analyst)).json()[0]
    assert tramontana_extra["row"]["id"] != (await client.get(f"{base(demo, PUESTO)}/extra-functions", headers=admin)).json()[0]["row"]["id"]

    # The functional view: E19200 also covered by the radio's extra function.
    level = (await client.get(f"{base(demo)}/functional", params={"parent": "E19000"}, headers=analyst)).json()
    switch = next(n for n in level["items"] if n["sns"] == "E19200")
    assert (switch["extra_count"], switch["extras_below"]) == (1, 1)
    holders = (await all_rows(client, demo, analyst, extra_sns="E19200"))["items"]
    assert [r["sns"] for r in holders] == ["E12300"]
    rows = (await all_rows(client, demo, analyst))["items"]
    [radio] = find(rows, "E12300")
    card = (await client.get(f"{base(demo)}/rows/{radio['id']}", headers=analyst)).json()
    assert [e["sns"] for e in card["extra_functions"]] == ["E19200"] and card["incompatibilities"] == []
    [pump_row] = find(rows, "A22110")
    assert len((await client.get(f"{base(demo)}/rows/{pump_row['id']}", headers=analyst)).json()["parts"]) == 3


async def test_the_parts_and_their_observations(client, demo):
    analyst = demo["people"]["analista"]
    pump, piston, gasket = await _article(PUMP), await _article(PISTON), await _article(GASKET)
    url = parts_url(pump)

    bad = await client.post(url, json={"cop": "1", "alp": "100", "quantity": "x"}, headers=analyst)
    assert bad.status_code == 422 and {(p["field"], p["code"]) for p in bad.json()["detail"]["problems"]} == {
        ("cop", "two_digits"), ("alp", "two_digits"), ("quantity", "not_a_number"), ("part_name", "part_identity_required"),
    }
    # A number that cannot be stored, Unicode digits: refused (never a 500, never a blank provisional article).
    bad = await client.post(url, json={"cop": "09", "noc": PISTON, "quantity": "1E-20000"}, headers=analyst)
    assert [(p["field"], p["code"]) for p in bad.json()["detail"]["problems"]] == [("quantity", "out_of_range")]
    bad = await client.post(url, json={"cop": "\u0660\u0661", "noc": PISTON}, headers=analyst)
    assert [(p["field"], p["code"]) for p in bad.json()["detail"]["problems"]] == [("cop", "two_digits")]
    bad = await client.post(url, json={"cop": "00", "noc": PISTON}, headers=analyst)
    assert [(p["field"], p["code"]) for p in bad.json()["detail"]["problems"]] == [("cop", "out_of_range")]

    def codes(part):
        return part["observation_codes"]

    own = (await client.post(url, json={"cop": "03", "article_id": str(pump.id), "quantity": 1}, headers=analyst)).json()
    assert "OP-001" in codes(own)
    # The pistón sits in the Tramontana's CONFUNFIS, where the pump is mounted too.
    in_cuf = (await client.post(url, json={"cop": "04", "noc": PISTON, "quantity": 0}, headers=analyst)).json()
    assert set(codes(in_cuf)) >= {"OP-004", "OP-005"}
    alone = (await client.post(url, json={"cop": "05", "alp": "03", "noc": PISTON, "quantity": 2}, headers=analyst)).json()
    assert "OP-006" in codes(alone)
    twice = (await client.post(url, json={"cop": "01", "alp": "00", "noc": GASKET, "quantity": 1}, headers=analyst)).json()
    assert "OP-003" in codes(twice)
    # A cycle of breakdowns: the gasket breaks down into the pump.
    cycle = (await client.post(parts_url(gasket), json={"cop": "01", "noc": PUMP, "quantity": 1}, headers=analyst)).json()
    assert "OP-002" in codes(cycle)
    listed = {p["id"]: p for p in (await client.get(url, headers=analyst)).json()}
    assert "OP-002" in codes(next(p for p in listed.values() if p["cop"] == "01" and p["alp"] == "00" and p["id"] != twice["id"]))

    # "Volver a ALP 00" and "Duplicar como alternativo".
    reset = await client.post(f"{url}/{alone['id']}/reset-alp", json={"version": alone["version"]}, headers=analyst)
    assert reset.status_code == 200 and reset.json()["alp"] == "00" and "OP-006" not in codes(reset.json())
    copy = await client.post(f"{url}/{alone['id']}/duplicate-alternative", json={"version": reset.json()["version"]}, headers=analyst)
    assert copy.status_code == 201, copy.text
    cop5 = sorted((p["alp"], p["article"]["noc"]) for p in (await client.get(url, headers=analyst)).json() if p["cop"] == "05")
    assert cop5 == [("01", PISTON), ("02", PISTON)]
    # Removing the copy, its ALP 01 alone goes back to 00.
    gone = await client.delete(f"{url}/{copy.json()['id']}", params={"version": copy.json()["version"], "confirm": True, "reset_alp": True}, headers=analyst)
    assert gone.status_code == 204
    assert [p["alp"] for p in (await client.get(url, headers=analyst)).json() if p["cop"] == "05"] == ["00"]

    # Editing goes with its version.
    stale = await client.patch(f"{url}/{in_cuf['id']}", json={"version": in_cuf["version"] - 1 or 99, "quantity": 2}, headers=analyst)
    assert stale.status_code == 409
    fixed = await client.patch(f"{url}/{in_cuf['id']}", json={"version": in_cuf["version"], "quantity": 2}, headers=analyst)
    assert fixed.status_code == 200 and "OP-004" not in codes(fixed.json())

    # An article that is a part cannot go; one with parts takes them along.
    denied = await client.delete(f"/api/articles/{gasket.id}", params={"version": gasket.version, "confirm": True}, headers=analyst)
    assert (denied.status_code, denied.json()["detail"]["code"]) == (409, "article_is_part")
    async with async_session_factory() as session:
        audited = await session.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == "article.part_added", AuditLog.entity_id == str(pump.id)))
    assert audited >= 6


async def test_part_totals_with_qty_and_alternative_cs(client, demo):
    """The parent in a hueco of QTY 2 under one of QTY 3 (6 in the CUF), and
    under two alternative CS (counted once)."""
    async with async_session_factory() as db:
        material = await db.get(Material, demo["materials"][TRAMONTANA].id)
        rows = await confunfis.live_rows(db, material.id)
        graph = confunfis.Graph(confunfis.graph_row(r) for r in rows)
        pump = await _article(PUMP)
        # The pump sits in A22110 01 00; the computer L41100 hangs from two alternative CS.
        computer = next(r for r in rows if r.sns == "L41100")
        part = ArticlePart(parent_article_id=computer.article_id, cop="01", alp="00", quantity=2)
        part.id = None
        totals = extras.part_totals(graph, rows, [part])
        assert totals[None] == 2 * graph.total(("L41100", "01")) == 2
        rings = next(r for r in rows if r.sns == "A21031")
        part = ArticlePart(parent_article_id=rings.article_id, cop="01", alp="00", quantity=2)
        part.id = None
        assert extras.part_totals(graph, rows, [part])[None] == 36
        assert pump.id in {r.article_id for r in rows}


async def test_functional_products(client, demo):
    analyst = demo["people"]["analista"]
    url = f"{base(demo)}/products"
    piston = await _article(PISTON)
    made = await client.post(url, json={"designation": "OTRO", "pol_code": "X-0000", "nae": "Q", "supply_unit": "ZZ", "unit": "QQ", "quantity": "N/A"}, headers=analyst)
    assert made.status_code == 201, made.text
    p = made.json()
    assert p["quantity"] is None and set(p["observation_codes"]) == {"OPF-001", "OPF-003", "OPF-004", "OPF-005"}
    named = (await client.post(url, json={"designation": "ACEITE", "pol_code": "O-1236", "nae": "N", "noc": PISTON, "supply_unit": "DR", "quantity": 1, "unit": "LI"}, headers=analyst)).json()
    assert named["observation_codes"] == ["OPF-002"] and named["article"]["id"] == str(piston.id)
    twin = (await client.post(url, json={"designation": "ACEITE", "pol_code": "O-1236", "nae": "N", "noc": PISTON, "supply_unit": "DR", "quantity": 1, "unit": "LI"}, headers=analyst)).json()
    assert set(twin["observation_codes"]) == {"OPF-002", "OPF-006"}
    # No provisional article for an unknown NOC.
    unknown = (await client.post(url, json={"designation": "X", "noc": "999999X999999"}, headers=analyst)).json()
    assert unknown["article"] is None
    used = (await client.get(f"/api/articles/{piston.id}", headers=analyst)).json()["where_used"]
    assert [(u["material_name"], u["pol_code"]) for u in used if u["kind"] == "functional_product"] == [(TRAMONTANA, "O-1236"), (TRAMONTANA, "O-1236")]

    edited = await client.patch(f"{url}/{p['id']}", json={"version": p["version"], "pol_code": "O-1236", "designation": "ACEITE LUBRICANTE MOTOR GRADO 15W/40", "nae": "N", "supply_unit": "DR", "unit": "LI"}, headers=analyst)
    assert edited.status_code == 200 and edited.json()["observation_codes"] == []
    assert (await client.patch(f"{url}/{p['id']}", json={"version": p["version"], "nae": "A"}, headers=analyst)).status_code == 409
    gone = await client.delete(f"{url}/{twin['id']}", params={"version": twin["version"], "confirm": True}, headers=analyst)
    assert gone.status_code == 204
    after = {x["id"]: x for x in (await client.get(url, headers=analyst)).json()}
    assert twin["id"] not in after and "OPF-006" not in after[named["id"]]["observation_codes"]


async def test_extra_functions(client, demo):
    analyst = demo["people"]["analista"]
    url = f"{base(demo)}/extra-functions"
    rows = (await all_rows(client, demo, analyst))["items"]
    [radio] = find(rows, "E12300")

    async def problem(body):
        res = await client.post(url, json={"position_id": radio["id"], "criterion": "otro", **body}, headers=analyst)
        assert res.status_code == 422, res.text
        return [p["code"] for p in res.json()["detail"]["problems"]]

    assert await problem({"sns": "Z99999"}) == ["sns_not_in_config"]
    assert await problem({"sns": "E12300"}) == ["sns_of_the_row"]
    assert await problem({"sns": "E19200"}) == ["sns_repeated"]
    assert await problem({"sns": "A21030", "criterion": "nada"}) == ["not_in_table"]

    made = await client.post(url, json={"position_id": radio["id"], "sns": "a21030", "criterion": "funcion_mas_critica"}, headers=analyst)
    assert made.status_code == 201 and made.json()["sns"] == "A21030"
    edited = await client.patch(f"{url}/{made.json()['id']}", json={"version": made.json()["version"], "comment": "  nota  "}, headers=analyst)
    assert edited.status_code == 200 and edited.json()["comment"] == "nota"
    gone = await client.delete(f"{url}/{made.json()['id']}", params={"version": edited.json()["version"], "confirm": True}, headers=analyst)
    assert gone.status_code == 204

    # The guard: removing the subcategories that bring E19200.
    async with async_session_factory() as db:
        material = await db.get(Material, demo["materials"][TRAMONTANA].id)
        config = await cuf.normalized_config(db, material)
        problem_ = await extras._extra_function_guard(db, material, set(config["E19200"]))
    assert problem_[0] == "subcategory_used_by_extra_function" and "E19200 (E12300 01 00)" in problem_[1]["rows"]


async def test_incompatibilities(client, demo):
    analyst = demo["people"]["analista"]
    url = f"{base(demo)}/incompatibilities"
    rows = (await all_rows(client, demo, analyst))["items"]
    a, b = find(rows, "A21030")[0], find(rows, "A22110")[0]

    same = await client.post(url, json={"row_a_id": a["id"], "row_b_id": a["id"], "kind": "excluye", "reason": "x"}, headers=analyst)
    assert same.status_code == 422
    blank = await client.post(url, json={"row_a_id": a["id"], "row_b_id": b["id"], "kind": "excluye", "reason": "   "}, headers=analyst)
    assert blank.status_code == 422
    made = await client.post(url, json={"row_a_id": a["id"], "row_b_id": b["id"], "kind": "excluye", "reason": "no caben"}, headers=analyst)
    assert made.status_code == 201 and made.json()["observation_codes"] == ["OI-001"]
    # "excluye" is symmetric: B-A is the same one.
    again = await client.post(url, json={"row_a_id": b["id"], "row_b_id": a["id"], "kind": "excluye", "reason": "otra vez"}, headers=analyst)
    assert (again.status_code, again.json()["detail"]["code"]) == (409, "incompatibility_exists")
    # "requiere" is directed: a cycle A -> B -> A is marked on both.
    ab = (await client.post(url, json={"row_a_id": a["id"], "row_b_id": b["id"], "kind": "requiere", "reason": "1"}, headers=analyst)).json()
    ba = (await client.post(url, json={"row_a_id": b["id"], "row_b_id": a["id"], "kind": "requiere", "reason": "2"}, headers=analyst)).json()
    listed = {i["id"]: i for i in (await client.get(url, headers=analyst)).json()}
    assert "OI-003" in listed[ab["id"]]["observation_codes"] and "OI-003" in listed[ba["id"]]["observation_codes"]
    card = (await client.get(f"{base(demo)}/rows/{b['id']}", headers=analyst)).json()
    assert len(card["incompatibilities"]) == 3 and card["incompatibility_count"] == 3

    # An "excluye" with an alternative on one side has no observation.
    alternative = find(rows, "A27010", "03", "01")[0]
    fine = (await client.post(url, json={"row_a_id": a["id"], "row_b_id": alternative["id"], "kind": "excluye", "reason": "ok"}, headers=analyst)).json()
    assert fine["observation_codes"] == []

    # A "requiere" towards a removed row (removed without the extension).
    async with async_session_factory() as db:
        material = await db.get(Material, demo["materials"][TRAMONTANA].id)
        await db.execute(Incompatibility.__table__.update().where(Incompatibility.id == ab["id"]).values(row_b_id=alternative["id"]))
        row = await db.get(PhysicalPosition, alternative["id"])
        row.deleted_at = func.now()
        await db.flush()
        await confunfis.refresh_observations(db, material)
        observed = (await db.get(Incompatibility, ab["id"])).observation_codes
        await db.rollback()
    assert "OI-002" in observed

    # Removing a row takes them along, each audited.
    res = await client.delete(f"{base(demo)}/rows/{b['id']}", params={"version": b["version"], "confirm": True}, headers=analyst)
    assert res.status_code == 204
    left = (await client.get(url, headers=analyst)).json()
    assert all(b["id"] not in (i["row_a"]["id"], i["row_b"]["id"]) for i in left)
    async with async_session_factory() as session:
        removed = await session.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == "confunfis.incompatibility_removed", AuditLog.after["with_row"].astext == b["id"]))
    assert removed == 3


async def test_removing_a_row_takes_its_extra_functions(client, demo):
    analyst = demo["people"]["analista"]
    [radio] = find((await all_rows(client, demo, analyst))["items"], "E12300")
    res = await client.delete(f"{base(demo)}/rows/{radio['id']}", params={"version": radio["version"], "confirm": True}, headers=analyst)
    assert res.status_code == 204
    assert (await client.get(f"{base(demo)}/extra-functions", headers=analyst)).json() == []
    async with async_session_factory() as session:
        audit = (await session.execute(select(AuditLog).where(AuditLog.action == "confunfis.extra_function_removed", AuditLog.after["with_row"].astext == radio["id"]))).scalars().all()
    assert [a.after for a in audit] == [{"with_row": radio["id"]}]


async def test_the_copy_is_remapped(client, demo):
    admin = demo["people"]["admin"]
    mid = demo["materials"][TRAMONTANA].id
    copy = await client.post(f"/api/materials/{mid}/copy", json={"name": "[test] copia E14", "noc": None, "copy_members": False}, headers=admin)
    assert copy.status_code == 201, copy.text
    target = f"/api/materials/{copy.json()['id']}/confunfis"
    rows = {r["id"]: r for r in (await client.get(f"{target}/rows", params={"page_size": 1000}, headers=admin)).json()["items"]}
    [extra] = (await client.get(f"{target}/extra-functions", headers=admin)).json()
    [item] = (await client.get(f"{target}/incompatibilities", headers=admin)).json()
    assert rows[extra["row"]["id"]]["sns"] == "E12300" and extra["sns"] == "E19200"
    assert (rows[item["row_a"]["id"]]["sns"], rows[item["row_b"]["id"]]["sns"]) == ("L41120", "L41130")
    products = (await client.get(f"{target}/products", headers=admin)).json()
    assert len(products) == 8 and {p["source"] for p in products} == {"copia"}
    # The parts are the article's: the same table, not copied.
    async with async_session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(ArticlePart).where(ArticlePart.deleted_at.is_(None))) == 3


async def test_permissions(client, demo):
    people = demo["people"]
    rows = (await all_rows(client, demo, people["analista"]))["items"]
    [radio] = find(rows, "E12300")
    pump = await _article(PUMP)
    for path in ("products", "extra-functions", "incompatibilities", "parts"):
        assert (await client.get(f"{base(demo)}/{path}", headers=people["observador"])).status_code == 200
        # Another material's analyst: the Tramontana is unknown (404).
        assert (await client.get(f"{base(demo)}/{path}", headers=people["outsider"])).status_code == 404
    for who in ("observador", "revisor"):
        headers = people[who]
        assert (await client.post(f"{base(demo)}/products", json={"designation": "X"}, headers=headers)).status_code == 403
        assert (await client.post(f"{base(demo)}/extra-functions", json={"position_id": radio["id"], "sns": "A21030", "criterion": "otro"}, headers=headers)).status_code == 403
        assert (await client.post(parts_url(pump), json={"cop": "09", "noc": PISTON}, headers=headers)).status_code == 403
    assert (await client.get(parts_url(pump), headers=people["observador"])).status_code == 200
    # The parts are the master's: articulos.editar in any material is enough.
    assert (await client.post(parts_url(pump), json={"cop": "09", "noc": PISTON, "quantity": 1}, headers=people["outsider"])).status_code == 201


async def test_the_seed_stays_idempotent(client, demo):
    assert await demo["seed"].seed() == 0
    async with async_session_factory() as session:
        for name in (TRAMONTANA, PUESTO):
            mid = demo["materials"][name].id
            counts = [
                await session.scalar(select(func.count()).select_from(model).where(model.material_id == mid, model.deleted_at.is_(None)))
                for model in (FunctionalProduct, ExtraFunction, Incompatibility)
            ]
            assert counts == [8, 1, 1]
        assert await session.scalar(select(func.count()).select_from(ArticlePart).where(ArticlePart.deleted_at.is_(None))) == 3
