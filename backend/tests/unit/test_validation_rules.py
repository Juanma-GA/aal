"""Every rule of the NT 10/17 validator (E16), pure: a CUF that complies
gives nothing, and each rule fires on its own case. Includes the three
cases of NT §9.1.8 that must not be taken for errors: a row under an
alternative (its CS has AL 01), a row with two alternative CS, and the
children of the CUF's own row (CS 000000 01 00)."""

import uuid
from decimal import Decimal
from types import SimpleNamespace

from app.services.parameters import PARAMETER_DEFAULTS
from app.validacion import engine
from app.validacion.catalog import BY_CODE, CATALOG

PARAMS = PARAMETER_DEFAULTS["confunfis"]
CODES = {"POL": {"O-1236"}, "NAE": {"N", "A", "E"}, "D155": {"DR"}, "UNIDAD_MEDIDA_PF": {"L", "LI"}}
CONFIG = {"A20000", "A21000", "A21010", "A22000", "A23000", "A23010", "B30000"}
_n = 0


def article(noc="123456X789012", **data):
    return SimpleNamespace(id=uuid.uuid4(), noc=noc, nombre="ART", findings=[], data=data)


def row(sns, co="01", al="00", cs=None, *, qty=1, name="PIEZA", fn="Hacer algo", ct="S", art=None, ref=None, notes=None):
    global _n
    _n += 1
    cs_sns, cs_co, cs_al = cs if cs else (None, None, None)
    a = art if art is not None else article()
    return SimpleNamespace(
        id=uuid.uuid4(), sns=sns, co=co, al=al, qty=qty, cs_sns=cs_sns, cs_co=cs_co, cs_al=cs_al, article_name=name, function_text=fn,
        ct_sigle=ct, article_id=a.id if a else None, article_reference_id=ref.id if ref else None, link_notes=notes or [],
        created_at=f"2026-01-01 00:00:{_n:06d}", _article=a, _ref=ref,
    )


ROOT = ("000000", "01", "00")


def cuf(*extra, products=(), parts=(), extras=(), incompatibilities=(), part_edges=None, config=CONFIG, mounted=(), file_cuf=None, data=None):
    rows = [row(*ROOT), row("A20000", cs=ROOT), row("A21000", cs=("A20000", "01", "00")), *extra]
    articles = {r._article.id: r._article for r in rows if r._article}
    references = {r._ref.id: r._ref for r in rows if r._ref}
    return engine.Context(
        rows=rows, config=set(config), params=PARAMS, articles=articles, references=references,
        article_findings={i: a.findings for i, a in articles.items()}, article_data=data or {i: a.data for i, a in articles.items()},
        products=list(products), parts=list(parts), part_edges=part_edges or {}, extras=list(extras), incompatibilities=list(incompatibilities),
        codes=CODES, mounted_sns=set(mounted), file_cuf=file_cuf,
    )


def found(ctx):
    return sorted({(f.code, f.problem) for f in engine.run(ctx)})


def codes(ctx):
    return sorted({f.code for f in engine.run(ctx)})


def test_every_rule_of_the_catalog_is_registered():
    assert set(engine.RULES) == {r.code for r in CATALOG}
    assert BY_CODE["CF-001"].severity == "bloqueante" and BY_CODE["CF-017"].severity == "aviso"


def test_a_cuf_that_complies_has_no_findings():
    assert found(cuf()) == []


def test_the_three_cases_of_9_1_8_are_not_errors():
    # 1. A row under an alternative: its CS has AL 01 (A22000 01 01 and 01 02 are the alternatives).
    under_alternative = [
        row("A22000", "01", "01", ROOT), row("A22000", "01", "02", ROOT), row("A23000", cs=("A22000", "01", "01")),
    ]
    # 2. One row with two alternative CS (the same SNS CO AL hanging from either).
    two_cs = [row("A23010", cs=("A21000", "01", "00")), row("A23010", cs=("A20000", "01", "00"))]
    # 3. The children of the CUF's own row: CS 000000 01 00.
    children_of_root = [row("B30000", cs=ROOT)]
    assert found(cuf(*under_alternative, *two_cs, *children_of_root)) == []


def test_cf001_outside_the_configuration():
    assert found(cuf(row("Z99999", cs=ROOT))) == [("CF-001", "outside")]


def test_cf002_sns_and_cs_format():
    assert ("CF-002", "sns") in found(cuf(row("a2", cs=ROOT)))
    # A malformed CS is CF-002 only, never CF-007 too.
    assert found(cuf(row("A21010", cs=("B300000000", "01", "00")))) == [("CF-002", "cs")]


def test_cf003_co_range():
    assert found(cuf(row("A21010", co="00", cs=ROOT))) == [("CF-003", "range")]


def test_cf004_alternatives():
    assert found(cuf(row("A21010", al="01", cs=ROOT))) == [("CF-004", "alone")]
    mixed = found(cuf(row("A21010", al="00", cs=ROOT), row("A21010", al="01", cs=ROOT)))
    assert ("CF-004", "mixed") in mixed


def test_cf005_qty():
    assert found(cuf(row("A21010", cs=ROOT, qty=None))) == [("CF-005", "missing")]
    assert found(cuf(row("A21010", cs=ROOT, qty=Decimal("1.5")))) == [("CF-005", "not_whole")]
    assert found(cuf(row("A21010", cs=ROOT, qty=0))) == [("CF-005", "not_positive")]


def test_cf006_qty_between_alternatives():
    got = found(cuf(row("A21010", al="01", cs=ROOT, qty=1), row("A21010", al="02", cs=ROOT, qty=2)))
    assert got == [("CF-006", "different")]


def test_cf007_cs_not_found():
    assert found(cuf(row("A21010", cs=("A24000", "01", "00")))) == [("CF-007", "not_found")]


def test_cf008_cs_missing():
    assert ("CF-008", "missing") in found(cuf(row("A21010")))


def test_cf009_the_principal_row():
    ctx = cuf()
    ctx.rows = ctx.rows[1:]
    ctx.__post_init__()
    assert ("CF-009", "missing") in found(ctx)
    # A mounted CUF: its own row at the SNS of its function, without CS, is fine.
    mounted = cuf(mounted={"A20000"})
    mounted.rows = [r for r in mounted.rows if r.sns != "000000"]
    for r in mounted.rows:
        if r.sns == "A20000":
            r.cs_sns = r.cs_co = r.cs_al = None
    mounted.__post_init__()
    assert found(mounted) == []
    assert ("CF-009", "several") in found(cuf(row(*ROOT)))


def test_cf010_cycle_of_cs():
    a, b = row("A21010", cs=("A22000", "01", "00")), row("A22000", cs=("A21010", "01", "00"))
    assert ("CF-010", "cycle") in found(cuf(a, b))


def test_cf011_and_cf012_identity():
    nameless = article(noc=None)
    parent = row("A21010", cs=ROOT, art=nameless)
    got = found(cuf(parent, row("A22000", cs=("A21010", "01", "00"))))
    assert ("CF-011", "no_identity") in got and ("CF-012", "no_identity") in got
    with_pn = SimpleNamespace(id=uuid.uuid4(), pn="X-1", ncage=None)
    assert found(cuf(row("A21010", cs=ROOT, art=article(noc=None), ref=with_pn))) == [("CF-012", "pn_without_ncage")]
    taken = row("A21010", cs=ROOT, notes=[{"code": "pn_taken", "params": {"pn": "X", "ncage": "AAAAA"}}])
    assert found(cuf(taken)) == [("CF-012", "pn_taken")]


def test_cf013_ncage_length():
    ref = SimpleNamespace(id=uuid.uuid4(), pn="X-1", ncage="ABC")
    assert found(cuf(row("A21010", cs=ROOT, art=article(noc=None), ref=ref))) == [("CF-013", "length")]


def test_cf014_name_and_function():
    assert found(cuf(row("A21010", cs=ROOT, fn=None))) == [("CF-014", "function")]
    assert found(cuf(row("A21010", cs=ROOT, name=" "))) == [("CF-014", "name")]


def test_cf015_only_the_second_occurrence():
    first, second = row("A21010", cs=ROOT), row("A21010", cs=ROOT)
    findings = [f for f in engine.run(cuf(first, second)) if f.code == "CF-015"]
    assert [f.entity_id for f in findings] == [str(second.id)]


def test_cf016_the_file_names_one_cuf():
    assert found(cuf(file_cuf={"cuf_noc": ["111", "111"]})) == []
    assert found(cuf(file_cuf={"cuf_noc": ["111", "222"]})) == [("CF-016", "different")]


def test_cf017_one_article_in_two_sns():
    shared = article()
    got = [f for f in engine.run(cuf(row("A21010", cs=ROOT, art=shared), row("A22000", cs=ROOT, art=shared))) if f.code == "CF-017"]
    assert len(got) == 1 and got[0].entity_type == "articulo" and got[0].row_id


def test_cf018_and_cf019_ct_sigle():
    assert found(cuf(row("A21010", cs=ROOT, ct=None))) == [("CF-018", "missing")]
    unit = article(snCtrlUniArt="N")
    assert found(cuf(row("A21010", cs=ROOT, art=unit))) == [("CF-019", "no_unit_control")]
    assert found(cuf(row("A21010", cs=ROOT, art=unit, ct="N"))) == []


def test_cf020_extra_functions():
    r = row("A21010", cs=ROOT)
    ok = SimpleNamespace(id=uuid.uuid4(), position_id=r.id, sns="A22000")
    assert found(cuf(r, extras=[ok])) == []
    same = SimpleNamespace(id=uuid.uuid4(), position_id=r.id, sns="A21010")
    outside = SimpleNamespace(id=uuid.uuid4(), position_id=r.id, sns="Z99999")
    assert found(cuf(r, extras=[same, outside])) == [("CF-020", "outside"), ("CF-020", "same_sns")]


def test_cf021_incompatibilities():
    a, b = row("A21010", cs=ROOT), row("A22000", cs=ROOT)
    alt1, alt2 = row("A23000", al="01", cs=ROOT), row("A23000", al="02", cs=ROOT)

    def inc(x, y, kind):
        return SimpleNamespace(id=uuid.uuid4(), row_a_id=x.id, row_b_id=y.id, kind=kind)

    assert found(cuf(a, alt1, alt2, incompatibilities=[inc(a, alt1, "excluye")])) == []
    assert found(cuf(a, b, incompatibilities=[inc(a, b, "excluye")])) == [("CF-021", "excluye_without_alternatives")]
    gone = SimpleNamespace(id=uuid.uuid4())
    assert found(cuf(a, incompatibilities=[inc(a, gone, "requiere")])) == [("CF-021", "requiere_removed")]
    assert ("CF-021", "requiere_cycle") in found(cuf(a, b, incompatibilities=[inc(a, b, "requiere"), inc(b, a, "requiere")]))


def part(parent, child=None, cop="01", alp="00", quantity=1, notes=None):
    return SimpleNamespace(id=uuid.uuid4(), parent_article_id=parent, part_article_id=child, cop=cop, alp=alp, quantity=quantity, link_notes=notes or [])


def test_tp001_parts():
    r = row("A21010", cs=ROOT)
    p, q, other = r.article_id, uuid.uuid4(), uuid.uuid4()
    assert found(cuf(r, parts=[part(p, q)])) == []
    assert ("TP-001", "self") in found(cuf(r, parts=[part(p, p)]))
    assert ("TP-001", "cycle") in found(cuf(r, parts=[part(p, q)], part_edges={p: {q}, q: {p}}))
    assert ("TP-001", "cop") in found(cuf(r, parts=[part(p, q, cop="00")]))
    assert ("TP-001", "quantity") in found(cuf(r, parts=[part(p, q, quantity=0)]))
    assert ("TP-001", "alone") in found(cuf(r, parts=[part(p, q, alp="01")]))
    assert ("TP-001", "duplicate") in found(cuf(r, parts=[part(p, q), part(p, other)]))
    # The part's article also sits in this CUF's CONFUNFIS.
    s = row("A22000", cs=ROOT)
    assert ("TP-001", "in_confunfis") in found(cuf(r, s, parts=[part(p, s.article_id)]))


def product(**values):
    base = {"designation": "ACEITE", "pol_code": "O-1236", "nae": "N", "noc": None, "supply_unit": "DR", "quantity": 1, "unit": "L"}
    return SimpleNamespace(id=uuid.uuid4(), **{**base, **values})


def test_pf001_products():
    assert found(cuf(products=[product()])) == []
    bad = product(pol_code="X-0000", nae="Q", supply_unit="ZZ", unit="QQ", quantity=0)
    assert found(cuf(products=[bad])) == [("PF-001", p) for p in ("nae", "pol", "quantity", "supply_unit", "unit")]
    assert found(cuf(products=[product(), product()])) == [("PF-001", "duplicate")]


def test_ar_rules_come_from_the_articles():
    flawed = article()
    flawed.findings = [{"code": "AR-002", "problem": "missing", "params": {}, "field": "x"}]
    findings = [f for f in engine.run(cuf(row("A21010", cs=ROOT, art=flawed))) if f.code.startswith("AR-")]
    assert [(f.code, f.entity_type, f.entity_id) for f in findings] == [("AR-002", "articulo", str(flawed.id))]


def test_the_parameters_set_the_ranges():
    ctx = cuf(row("A21010", co="50", cs=ROOT))
    assert found(ctx) == []
    ctx.params = {**PARAMS, "co": {"min": 1, "max": 40}}
    assert found(ctx) == [("CF-003", "range")]
