"""The reference tables seed (E03): the real file passes every check with
the exact counts, its codes are text, and each check catches what it is
for."""

from dataclasses import replace

import pytest

from app.services.reference_seed import SeedValue, check_seed, read_seed

COUNTS = {
    "D106": 18, "D107": 15, "D112": 82, "D113": 12, "D114": 13, "D155": 161, "POL": 161, "NIVEL_FUNCIONAL": 6,
    "M101": 13, "OPERATIVIDAD": 3, "CRITICIDAD": 3, "ESCALON": 4, "TIPO_MANTENIMIENTO": 2, "MODO_EJECUCION": 3, "NAE": 3,
}


@pytest.fixture(scope="module")
def seed():
    return read_seed()


def tables(seed):
    return {t.code: t for t in seed.tables}


def test_the_real_seed_passes_with_the_exact_counts(seed):
    assert check_seed(seed) == []
    assert {t.code: len(t.values) for t in seed.tables} == COUNTS
    assert len(seed.fields) == 30


def test_codes_are_text_with_their_zeros(seed):
    t = tables(seed)
    assert all(isinstance(v.code, str) for table in seed.tables for v in table.values)
    assert {"0", "1"} <= {v.code for v in t["D107"].values}
    assert {"0", "1"} <= {v.code for v in t["D113"].values}
    assert {"01", "02", "09"} <= {v.code for v in t["D114"].values}


def test_attributes_and_their_schema(seed):
    t = tables(seed)
    kinds = {v.code: v.attributes["tipo"] for v in t["D114"].values}
    assert {c for c, k in kinds.items() if k == "temporal"} == {"02", "03", "04", "05"}
    assert t["D114"].attribute_schema[0]["options"] == [{"code": "temporal", "name": "Temporal"}, {"code": "no_temporal", "name": "No temporal"}]
    assert all(v.definition for v in t["D155"].values)
    assert sum(v.attributes["marca_asterisco"] for v in t["D155"].values) == 48


def _with_values(seed, code, values):
    return replace(seed, tables=[replace(t, values=values) if t.code == code else t for t in seed.tables])


def test_a_code_that_is_not_text_is_refused(seed):
    d114 = tables(seed)["D114"]
    bad = _with_values(seed, "D114", d114.values + [SeedValue(code=9, description="Nueve", definition=None, attributes={"tipo": "temporal"})])
    assert check_seed(bad) == ["D114: the code 9 is not text (quote it in the YAML)"]


def test_duplicate_codes_are_refused(seed):
    d107 = tables(seed)["D107"]
    bad = _with_values(seed, "D107", d107.values + [d107.values[0]])
    assert check_seed(bad) == ["D107: duplicate value '0'"]


def test_attributes_that_do_not_fit_are_refused(seed):
    d114 = tables(seed)["D114"]
    wrong = [replace(d114.values[0], attributes={"tipo": "otro"}), replace(d114.values[1], attributes={})] + d114.values[2:]
    problems = check_seed(_with_values(seed, "D114", wrong))
    assert [p.split(":")[1].split()[0] for p in problems] == ["attribute_option_invalid", "attribute_required"]


def test_a_field_with_an_unknown_reference_table_is_refused(seed):
    fields = [dict(f, reference_table_code="D999") if f["prisma_code"] == "cdPolEl" else f for f in seed.fields]
    assert check_seed(replace(seed, fields=fields)) == ["article field cdPolEl: unknown reference table D999"]
