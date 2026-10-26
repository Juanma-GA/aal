"""The CONFUNFIS book (E15, NT 10/17 Anexo XI) with the whole demo loaded:
the figures of the encargo §2.3 (the demo imported into the Tramontana, a
QTY changed and a row removed in both modes, the demo into a new empty CUF
whose CUF differs), the exports against the demo file cell by cell, the
round trips (Anexo XI and Libro AAL), the tolerances of the reader (the
other header of the products, no parts sheet, unknown sheets, the root's
CS, CO/AL as numbers), the transaction, the permissions and the empty
template filled by a subcontractor."""

import io
from collections import Counter
from pathlib import Path

import openpyxl
import pytest_asyncio
from sqlalchemy import delete, func, select

from app.db.base import async_session_factory
from app.models import AuditLog, ImportJob, Material, PhysicalPosition
from app.services import confunfis_extras as extras
from integration.test_catalog import catalog  # noqa: F401
from integration.test_confunfis import PUESTO, TRAMONTANA, base, demo  # noqa: F401

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
DEMO_BOOK = Path(__file__).resolve().parents[3] / "demo" / "CONFUNFIS_DEMO_TRAMONTANA.xlsx"
NEW_CUF = "[test] CUF vacío E15"


def _book(data: bytes) -> openpyxl.Workbook:
    return openpyxl.load_workbook(io.BytesIO(data))


def _bytes(book: openpyxl.Workbook) -> bytes:
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()


def _cells(ws) -> list[tuple]:
    return [tuple(c.value for c in row) for row in ws.iter_rows()]


async def analysed(client, demo, headers, data, name=TRAMONTANA, mode="merge"):
    res = await client.post(f"{base(demo, name)}/import", params={"mode": mode}, files={"file": ("LIBRO.xlsx", data, XLSX)}, headers=headers)
    assert res.status_code == 202, res.text
    job = (await client.get(f"/api/import-jobs/{res.json()['id']}", headers=headers)).json()
    assert job["status"] == "analyzed", job
    return job


def sheet_counts(job, sheet):
    s = job["report"]["sheets"][sheet]
    return {k: len(s[k]) for k in ("new", "modified", "unchanged", "removed", "rejected")}


async def apply(client, demo, headers, job, name=TRAMONTANA, **body):
    return await client.post(f"{base(demo, name)}/import/{job['id']}/apply", json=body, headers=headers)


@pytest_asyncio.fixture(autouse=True)
async def _jobs(demo):
    """The import jobs go before the demo's materials do."""
    yield
    async with async_session_factory() as session:
        await session.execute(delete(ImportJob).where(ImportJob.material_id.is_not(None)))
        await session.commit()


@pytest_asyncio.fixture
async def empty_cuf(client, demo):
    """A new CUF with the subcategories 0601 + 0201 + 0102 and no CONFUNFIS."""
    admin = demo["people"]["admin"]
    made = (await client.post("/api/materials", json={"name": NEW_CUF, "description": "E15"}, headers=admin)).json()
    current = (await client.get(f"/api/materials/{made['id']}/cuf", headers=admin)).json()
    res = await client.put(f"/api/materials/{made['id']}/subcategories", json={"version": current["version"], "codes": ["0601", "0201", "0102"]}, headers=admin)
    assert res.status_code == 200, res.text
    async with async_session_factory() as session:
        demo["materials"][NEW_CUF] = await session.get(Material, made["id"])
    yield made
    async with async_session_factory() as session:
        await session.execute(delete(ImportJob).where(ImportJob.material_id == made["id"]))
        await session.execute(delete(Material).where(Material.name == NEW_CUF))
        await session.commit()


async def test_the_demo_into_the_tramontana_changes_nothing(client, demo):
    job = await analysed(client, demo, demo["people"]["analista"], DEMO_BOOK.read_bytes())
    report = job["report"]
    assert sheet_counts(job, "CON_FUN_FIS") == {"new": 0, "modified": 0, "unchanged": 46, "removed": 0, "rejected": 0}
    assert sheet_counts(job, "TABLA PRODUCTOS FUNCIONALES") == {"new": 0, "modified": 0, "unchanged": 8, "removed": 0, "rejected": 0}
    assert sheet_counts(job, "TABLA DE PARTES") == {"new": 0, "modified": 0, "unchanged": 3, "removed": 0, "rejected": 0}
    assert report["cuf"]["differs"] is False and report["ignored_sheets"] == []
    assert report["result"]["provisional_articles"] == [] and report["result"]["new_references"] == []
    assert report["result"]["observations"]["OPF-004"] == 1


def _changed_demo() -> tuple[bytes, str]:
    """The demo with a QTY changed (the radiator: 1 -> 2) and a row removed (the brake pincer)."""
    book = _book(DEMO_BOOK.read_bytes())
    ws = book["CON_FUN_FIS"]
    rows = list(ws.iter_rows(min_row=3))
    radiator = next(r for r in rows if r[4].value == "A22120")
    radiator[7].value = 2
    pincer = next(r for r in rows if r[4].value == "B32010")
    ws.delete_rows(pincer[0].row)
    return _bytes(book), "B32010"


async def test_a_qty_changed_and_a_row_removed_in_both_modes(client, demo):
    analyst, admin = demo["people"]["analista"], demo["people"]["admin"]
    data, removed = _changed_demo()
    merge = await analysed(client, demo, analyst, data)
    assert sheet_counts(merge, "CON_FUN_FIS") == {"new": 0, "modified": 1, "unchanged": 45, "removed": 0, "rejected": 0}
    assert merge["report"]["sheets"]["CON_FUN_FIS"]["modified"][0]["changes"] == [{"field": "qty", "header": "qty", "before": "1", "after": "2"}]

    # Sustituir: the admin only, and the CUF's name typed.
    assert (await client.post(f"{base(demo)}/import", params={"mode": "replace"}, files={"file": ("L.xlsx", data, XLSX)}, headers=analyst)).status_code == 403
    replace = await analysed(client, demo, admin, data, mode="replace")
    assert sheet_counts(replace, "CON_FUN_FIS") == {"new": 0, "modified": 1, "unchanged": 44, "removed": 1, "rejected": 0}
    assert replace["report"]["sheets"]["CON_FUN_FIS"]["removed"][0]["key"].startswith(removed)
    refused = await apply(client, demo, admin, replace, confirm_name="otro nombre")
    assert (refused.status_code, refused.json()["detail"]["code"]) == (409, "import_replace_not_confirmed")
    done = await apply(client, demo, admin, replace, confirm_name=TRAMONTANA)
    assert done.status_code == 200, done.text
    async with async_session_factory() as session:
        mid = demo["materials"][TRAMONTANA].id
        live = (await session.execute(select(PhysicalPosition).where(PhysicalPosition.material_id == mid, PhysicalPosition.deleted_at.is_(None)))).scalars().all()
        audited = await session.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == "confunfis.row_deleted", AuditLog.material_id == mid))
    assert len(live) == 45 and not [r for r in live if r.sns == removed] and audited >= 1
    assert next(r for r in live if r.sns == "A22120").qty == 2
    # Analysed before, the merge job is stale now.
    stale = await apply(client, demo, analyst, merge)
    assert (stale.status_code, stale.json()["detail"]["code"]) == (409, "import_stale")


async def test_the_demo_into_a_new_empty_cuf(client, demo, empty_cuf):
    admin = demo["people"]["admin"]
    job = await analysed(client, demo, admin, DEMO_BOOK.read_bytes(), name=NEW_CUF)
    assert sheet_counts(job, "CON_FUN_FIS")["new"] == 46
    assert sheet_counts(job, "TABLA PRODUCTOS FUNCIONALES")["new"] == 8
    assert sheet_counts(job, "TABLA DE PARTES") == {"new": 0, "modified": 0, "unchanged": 3, "removed": 0, "rejected": 0}
    assert job["report"]["cuf"]["differs"] is True and {"code": "cuf_differs"} in job["report"]["notices"]
    refused = await apply(client, demo, admin, job, name=NEW_CUF)
    assert (refused.status_code, refused.json()["detail"]["code"]) == (409, "import_cuf_not_confirmed")
    done = await apply(client, demo, admin, job, name=NEW_CUF, confirm_cuf=True)
    assert done.status_code == 200, done.text
    rows = (await client.get(f"{base(demo, NEW_CUF)}/rows", params={"page_size": 1000}, headers=admin)).json()
    assert rows["total"] == 46 and {r["source"] for r in rows["items"]} == {"import"}
    assert len((await client.get(f"{base(demo, NEW_CUF)}/products", headers=admin)).json()) == 8
    # Its audit says the import job.
    async with async_session_factory() as session:
        entry = (await session.execute(select(AuditLog).where(AuditLog.action == "confunfis.row_created", AuditLog.material_id == empty_cuf["id"]).limit(1))).scalar_one()
    assert entry.after["origin"]["import_job"] == job["id"]


async def test_the_exports_are_the_demo_file(client, demo):
    analyst, admin = demo["people"]["analista"], demo["people"]["admin"]
    data = (await client.get(f"{base(demo)}/export", params={"kind": "anexo"}, headers=analyst)).content
    exported, original = _book(data), _book(DEMO_BOOK.read_bytes())
    assert exported.sheetnames == original.sheetnames
    for ws in original:
        mine = _cells(exported[ws.title])
        theirs = _cells(ws)
        # Headers cell by cell; the rows the same values, in the tree's order (the demo is not sorted): a multiset.
        assert mine[:2] == theirs[:2], ws.title
        assert Counter(mine[2:]) == Counter(theirs[2:]), ws.title
    fun = exported["CON_FUN_FIS"]
    assert {str(r) for r in fun.merged_cells.ranges} == {"A1:D1", "F1:N1", "O1:Q1"}
    assert fun["F3"].number_format == "@" and fun["E3"].value == "000000" and fun["O3"].value is None
    # The Puesto de mando: the same but its CUF columns.
    puesto = _book((await client.get(f"{base(demo, PUESTO)}/export", params={"kind": "anexo"}, headers=admin)).content)
    material = demo["materials"][PUESTO]
    strip = lambda rows: Counter(r[4:] for r in rows)  # noqa: E731
    assert strip(_cells(puesto["CON_FUN_FIS"])[2:]) == strip(_cells(original["CON_FUN_FIS"])[2:])
    assert {r[:4] for r in _cells(puesto["CON_FUN_FIS"])[2:]} == {(material.noc, material.name, material.part_number, material.ncage)}


async def test_round_trips(client, demo):
    analyst = demo["people"]["analista"]
    for kind in ("anexo", "aal"):
        data = (await client.get(f"{base(demo)}/export", params={"kind": kind}, headers=analyst)).content
        job = await analysed(client, demo, analyst, data)
        c = job["counts"]
        assert (c["new"], c["modified"], c["removed"], c["rejected"], c["errors"]) == (0, 0, 0, 0, 0), (kind, c)
        if kind == "aal":
            assert sheet_counts(job, "FUNCIONES ADICIONALES")["unchanged"] == 1 and sheet_counts(job, "INCOMPATIBILIDADES")["unchanged"] == 1


async def test_the_reader_tolerates_the_official_book(client, demo):
    """LÍQUIDOS FUNCIONALES, no TABLA DE PARTES, auxiliary sheets, the root's
    CS as 000000 01 00, CO / AL as numbers, the official merged headers."""
    book = _book(DEMO_BOOK.read_bytes())
    book["TABLA PRODUCTOS FUNCIONALES"]["D1"].value = "LÍQUIDOS FUNCIONALES"
    book["CON_FUN_FIS"].merge_cells("A1:D1")
    del book["TABLA DE PARTES"]
    book.create_sheet("VTER_SubSistema")
    book.create_sheet("Hoja1")["A1"] = "D155"
    ws = book["CON_FUN_FIS"]
    root = next(r for r in ws.iter_rows(min_row=3) if r[4].value == "000000")
    root[14].value, root[15].value, root[16].value = "000000", "01", "00"
    for r in ws.iter_rows(min_row=3):
        if r[5].value == "01":
            r[5].value = 1
    job = await analysed(client, demo, demo["people"]["analista"], _bytes(book))
    assert job["report"]["ignored_sheets"] == ["VTER_SubSistema", "Hoja1"]
    assert "TABLA DE PARTES" not in job["report"]["sheets"]
    assert sheet_counts(job, "CON_FUN_FIS")["unchanged"] == 46 and sheet_counts(job, "TABLA PRODUCTOS FUNCIONALES")["unchanged"] == 8
    assert job["counts"]["errors"] == 0


async def test_the_duplicates_are_matched_in_order(client, demo):
    """B32020 01 00 is twice in the demo (OF-004): changing the second one's QTY modifies the second one."""
    book = _book(DEMO_BOOK.read_bytes())
    twins = [r for r in book["CON_FUN_FIS"].iter_rows(min_row=3) if r[4].value == "B32020"]
    assert len(twins) == 2
    twins[1][7].value = 9
    job = await analysed(client, demo, demo["people"]["analista"], _bytes(book))
    assert sheet_counts(job, "CON_FUN_FIS")["modified"] == 1 and job["report"]["sheets"]["CON_FUN_FIS"]["modified"][0]["row"] == twins[1][0].row


async def test_the_import_is_one_transaction(client, demo, monkeypatch):
    """A failure in the third sheet leaves the first two as they were."""
    analyst = demo["people"]["analista"]
    data, _removed = _changed_demo()
    book = _book(data)
    parts = book["TABLA DE PARTES"]
    parts["I3"].value = 5
    book["TABLA PRODUCTOS FUNCIONALES"]["I3"].value = 30
    job = await analysed(client, demo, analyst, _bytes(book))
    assert (sheet_counts(job, "CON_FUN_FIS")["modified"], sheet_counts(job, "TABLA PRODUCTOS FUNCIONALES")["modified"], sheet_counts(job, "TABLA DE PARTES")["modified"]) == (1, 1, 1)

    async def broken(*args, **kwargs):
        raise RuntimeError("the third sheet fails")

    monkeypatch.setattr(extras, "save_part", broken)
    failed = await apply(client, demo, analyst, job)
    assert failed.status_code == 500
    rows = (await client.get(f"{base(demo)}/rows", params={"sns": "A22120"}, headers=analyst)).json()["items"]
    products = (await client.get(f"{base(demo)}/products", headers=analyst)).json()
    assert rows[0]["qty"] == "1" and not any(p["quantity"] == "30" for p in products)


async def test_permissions(client, demo):
    people = demo["people"]
    data = DEMO_BOOK.read_bytes()
    for who in ("observador", "revisor"):
        assert (await client.post(f"{base(demo)}/import", files={"file": ("L.xlsx", data, XLSX)}, headers=people[who])).status_code == 403
        assert (await client.get(f"{base(demo)}/export", headers=people[who])).status_code == 200
    assert (await client.get(f"{base(demo)}/export", headers=people["outsider"])).status_code == 404


async def test_the_empty_template_filled_by_a_subcontractor(client, demo, empty_cuf):
    admin = demo["people"]["admin"]
    data = (await client.get(f"{base(demo, NEW_CUF)}/export", params={"kind": "plantilla"}, headers=admin)).content
    book = _book(data)
    assert book.sheetnames == ["CON_FUN_FIS", "TABLA PRODUCTOS FUNCIONALES", "TABLA DE PARTES", "SNS PERMITIDOS", "TABLAS"]
    fun = book["CON_FUN_FIS"]
    assert [c.value for c in fun[3]][4:7] == ["000000", "01", "00"]
    lists = {str(v.sqref).split(":")[0] for v in fun.data_validations.dataValidation}
    assert {"E3", "N3"} <= lists
    allowed = [r[0].value for r in book["SNS PERMITIDOS"].iter_rows(min_row=2)]
    assert "A20000" in allowed and "A21030" in allowed
    material = demo["materials"][NEW_CUF]
    cuf = [material.noc, material.name, material.part_number, material.ncage]
    fun.append([*cuf, "A20000", "01", "00", 1, None, None, None, "MOTOR DE PRUEBA", "Mover el vehículo", "S", "000000", "01", "00"])
    fun.append([*cuf, "A21030", "01", "00", 6, None, None, None, "PISTÓN DE PRUEBA", "Comprimir", "N", "A20000", "01", "00"])
    job = await analysed(client, demo, admin, _bytes(book), name=NEW_CUF)
    assert sheet_counts(job, "CON_FUN_FIS")["new"] == 3 and job["report"]["ignored_sheets"] == ["SNS PERMITIDOS", "TABLAS"]
    assert (await apply(client, demo, admin, job, name=NEW_CUF)).status_code == 200
    rows = (await client.get(f"{base(demo, NEW_CUF)}/rows", params={"page_size": 100}, headers=admin)).json()["items"]
    assert sorted(r["sns"] for r in rows) == ["000000", "A20000", "A21030"]
    assert next(r for r in rows if r["sns"] == "A21030")["total"] == "6"
