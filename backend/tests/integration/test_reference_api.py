"""/api/reference-tables and /api/article-fields (E03): anyone signed in
reads, only an admin edits (with optimistic locking and audit), nothing is
deleted, and must_be_in() checks codes for the modules' schemas."""

from typing import Annotated

import pytest
from sqlalchemy import select

from app.db.base import async_session_factory
from app.models import AuditLog
from app.schemas.common import StrictModel
from app.services.reference import must_be_in, resolve, validate_references
from helpers import bearer, login
from integration.reference_restore import restore_tables  # noqa: F401


@pytest.fixture
async def tokens(client, factory):
    admin, _ = await login(client, await factory.user(is_admin=True))
    analyst, _ = await login(client, await factory.user())
    return bearer(admin), bearer(analyst)


async def _value(client, headers, table, code):
    values = (await client.get(f"/api/reference-tables/{table}/values", headers=headers)).json()
    return next(v for v in values if v["code"] == code)


async def test_any_signed_in_user_reads_the_tables(client, tokens):
    _admin, analyst = tokens
    tables = (await client.get("/api/reference-tables", headers=analyst)).json()
    assert len(tables) == 15
    by_code = {t["code"]: t for t in tables}
    assert (by_code["D155"]["value_count"], by_code["D155"]["active_count"]) == (161, 161)
    assert by_code["D114"]["attribute_schema"][0]["name"] == "Tipo de control"
    d114 = (await client.get("/api/reference-tables/D114/values", headers=analyst)).json()
    assert [v["code"] for v in d114][:4] == ["02", "03", "04", "05"]
    assert {v["code"]: v["attributes"]["tipo"] for v in d114}["01"] == "no_temporal"
    assert (await client.get("/api/reference-tables")).status_code == 401
    missing = await client.get("/api/reference-tables/NOPE/values", headers=analyst)
    assert (missing.status_code, missing.json()["detail"]["code"]) == (404, "reference_table_not_found")


async def test_text_and_state_filters(client, tokens):
    _admin, analyst = tokens
    found = (await client.get("/api/reference-tables/D155/values", params={"q": "doscientos"}, headers=analyst)).json()
    assert {v["code"] for v in found} >= {"AA", "ZF"}
    # LIKE wildcards are literal text.
    assert (await client.get("/api/reference-tables/D155/values", params={"q": "%"}, headers=analyst)).json() == []
    assert len((await client.get("/api/reference-tables/D155/values", params={"active": "false"}, headers=analyst)).json()) == 0


async def test_only_an_admin_edits(client, tokens, restore_tables):
    await restore_tables("D112")
    _admin, analyst = tokens
    ea = await _value(client, analyst, "D112", "EA")
    for method, path, body in (
        ("post", "/api/reference-tables/D112/values", {"code": "QQ", "description": "x"}),
        ("patch", f"/api/reference-tables/D112/values/{ea['id']}", {"version": ea["version"], "description": "x"}),
        ("put", "/api/reference-tables/D112/order", {"version": 1, "value_ids": []}),
    ):
        res = await getattr(client, method)(path, json=body, headers=analyst)
        assert (res.status_code, res.json()["detail"]["code"]) == (403, "admin_required")


async def test_create_edit_deactivate_with_locking_and_audit(client, tokens, restore_tables):
    await restore_tables("D112")
    admin, analyst = tokens
    created = await client.post("/api/reference-tables/D112/values", json={"code": " QQ ", "description": "Unidad de prueba"}, headers=admin)
    assert created.status_code == 201, created.text
    value = created.json()
    assert (value["code"], value["sort_order"], value["is_active"]) == ("QQ", 83, True)
    dup = await client.post("/api/reference-tables/D112/values", json={"code": "QQ", "description": "otra"}, headers=admin)
    assert (dup.status_code, dup.json()["detail"]["code"]) == (409, "reference_value_exists")

    path = f"/api/reference-tables/D112/values/{value['id']}"
    edited = (await client.patch(path, json={"version": 1, "description": "Editada", "definition": "Una definición"}, headers=admin)).json()
    assert (edited["description"], edited["definition"], edited["version"]) == ("Editada", "Una definición", 2)
    stale = await client.patch(path, json={"version": 1, "description": "Otra"}, headers=admin)
    assert (stale.status_code, stale.json()["detail"]) == (409, {"code": "version_conflict", "current_version": 2})

    off = (await client.patch(path, json={"version": 2, "is_active": False}, headers=admin)).json()
    assert off["is_active"] is False
    # Still there, marked inactive, and it still resolves (HR9).
    assert (await _value(client, analyst, "D112", "QQ"))["is_active"] is False
    async with async_session_factory() as session:
        assert (await resolve(session, "D112", "QQ")).description == "Editada"
        actions = (await session.execute(select(AuditLog.action).where(AuditLog.entity_id == value["id"]).order_by(AuditLog.created_at))).scalars().all()
    assert actions == ["reference_value.created", "reference_value.updated", "reference_value.deactivated"]
    # No physical delete: there is no such route.
    assert (await client.delete(path, headers=admin)).status_code == 405


async def test_attributes_follow_the_tables_schema(client, tokens, restore_tables):
    await restore_tables("D114")
    admin, _ = tokens
    url = "/api/reference-tables/D114/values"
    cases = [
        ({"code": "99", "description": "x"}, "attribute_required"),
        ({"code": "99", "description": "x", "attributes": {"tipo": "otro"}}, "attribute_option_invalid"),
        ({"code": "99", "description": "x", "attributes": {"tipo": "temporal", "color": "rojo"}}, "attribute_unknown"),
        ({"code": "99", "description": "x", "attributes": {"tipo": True}}, "attribute_invalid"),
    ]
    for body, code in cases:
        res = await client.post(url, json=body, headers=admin)
        assert (res.status_code, res.json()["detail"]["code"]) == (422, code), body
    ok = await client.post(url, json={"code": "99", "description": "Prueba", "attributes": {"tipo": "temporal"}}, headers=admin)
    assert ok.status_code == 201 and ok.json()["attributes"] == {"tipo": "temporal"}


async def test_reorder_needs_every_value_and_the_tables_version(client, tokens, restore_tables):
    await restore_tables("NAE")
    admin, analyst = tokens
    table = (await client.get("/api/reference-tables/NAE", headers=analyst)).json()
    values = (await client.get("/api/reference-tables/NAE/values", headers=analyst)).json()
    ids = [v["id"] for v in values]
    partial = await client.put("/api/reference-tables/NAE/order", json={"version": table["version"], "value_ids": ids[:2]}, headers=admin)
    assert partial.json()["detail"]["code"] == "reference_order_mismatch"
    reordered = await client.put("/api/reference-tables/NAE/order", json={"version": table["version"], "value_ids": ids[::-1]}, headers=admin)
    assert [v["code"] for v in reordered.json()] == ["E", "A", "N"]
    again = await client.put("/api/reference-tables/NAE/order", json={"version": table["version"], "value_ids": ids}, headers=admin)
    assert again.json()["detail"]["code"] == "version_conflict"


async def test_article_fields(client, tokens):
    _admin, analyst = tokens
    fields = (await client.get("/api/article-fields", headers=analyst)).json()
    assert len(fields) == 30
    by_code = {f["prisma_code"]: f for f in fields}
    assert (by_code["cdConjRep"]["reference_table_code"], by_code["cdConjRep"]["reference_table_name"]) == ("D107", "Nivel estructural de artículo")
    assert by_code["cdPolEl"]["reference_table_code"] == "POL"
    assert by_code["imEstdArt"]["decimals"] == 2


class _ArticleIn(StrictModel):
    security: Annotated[str | None, must_be_in("D106")] = None
    unit: Annotated[str | None, must_be_in("D112")] = None


async def test_must_be_in_for_the_modules_schemas(restore_tables):
    await restore_tables("D112")
    from fastapi import HTTPException
    from sqlalchemy import update

    from app.models import ReferenceValue

    async with async_session_factory() as session:
        await validate_references(session, _ArticleIn(security="U", unit="EA"))
        with pytest.raises(HTTPException) as exc:
            await validate_references(session, _ArticleIn(security="Z"))
        assert exc.value.detail == {"code": "reference_value_unknown", "field": "security", "table": "D106"}
        await session.execute(update(ReferenceValue).where(ReferenceValue.table_code == "D112", ReferenceValue.code == "EA").values(is_active=False))
        with pytest.raises(HTTPException) as exc:
            await validate_references(session, _ArticleIn(unit="EA"))
        assert exc.value.detail["code"] == "reference_value_inactive"
        # The value the record already had is still accepted.
        await validate_references(session, _ArticleIn(unit="EA"), current={"unit": "EA"})
        await session.rollback()
