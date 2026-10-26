"""The AR rules of an article (E12, app/validacion/articulos.py), one by
one, with articles that keep and that break them; the definitions are the
seed's (article_field_definition), so a field's importance or table comes
from there, never from the rule."""

from decimal import Decimal

import pytest

from app.services.article_fields import FieldDef
from app.services.reference_seed import read_field_extras, read_seed
from app.validacion.articulos import RULES, LifeControl, autocorrect, check

REFS = {
    "D106": {"U": True}, "D107": {"0": True, "3": True, "7": True}, "D112": {"KG": True, "CM": True, "LI": True, "XX": False},
    "D113": {"S": True, "B": True}, "D114": {"01": True, "03": True}, "D155": {"EA": True}, "POL": {},
}


@pytest.fixture(scope="module")
def defs() -> dict[str, FieldDef]:
    extras = read_field_extras()
    out = {}
    for f in read_seed().fields:
        e = extras[f["prisma_code"]]
        out[f["prisma_code"]] = FieldDef(
            prisma=f["prisma_code"], name=f["name"], header=e["header"], importance=f["importance"], guide_field=f["guide_field"],
            data_type=f["data_type"], length=f["length"], decimals=f["decimals"], table=f["reference_table_code"],
            allowed_values=tuple(e["allowed_values"]) if e["allowed_values"] else None, help=e["help"], sort_order=f["sort_order"],
        )
    return out


def good() -> dict:
    """An article that keeps every rule."""
    return {
        "cdART": "100533X901201", "NomArt": "PISTÓN", "cdConjRep": "3", "cdSegArt": "U", "snRepaArt": "N", "snConsuArt": "N",
        "cdUsumExtrArt": "EA", "snCtrlUniArt": "N", "imEstdArt": Decimal("10"), "snDocuAdjUArt": "N", "caPesoArt": Decimal("1.2"),
        "cdUnidPesoArt": "KG", "caLargoArt": None, "caAnchoArt": None, "caAltoArt": None, "cdUnidLongArt": None, "caVoluArt": None,
        "cdUnidVoluArt": None, "cdCtrlUniArt": None, "snCtrlVidaArt": "N", "snMtN1Art": "N", "snMtN2Art": "N", "snMtN3Art": "N",
        "snMtN4Art": "N", "vaUsoArt": None, "snCnfgArt": "N", "snMtPreArt": "N", "cdPolEl": None,
    }


def codes(found) -> list[tuple[str, str, str]]:
    return sorted((f["code"], f["field"], f["problem"]) for f in found)


def test_a_good_article_has_no_findings(defs):
    assert check(good(), [], defs, REFS) == []


def test_every_rule_is_declared_with_its_severity():
    assert {c: r.severity for c, r in RULES.items()} == {
        "AR-001": "aviso", "AR-002": "bloqueante", "AR-003": "bloqueante", "AR-004": "bloqueante",
        "AR-005": "bloqueante", "AR-006": "bloqueante", "AR-007": "aviso", "AR-008": "autocorreccion",
    }
    assert all(r.guide_fields for r in RULES.values())


def test_ar_001_required_conditional_and_tables(defs):
    a = {**good(), "cdART": None, "cdUsumExtrArt": None, "cdUnidPesoArt": "XX", "cdConjRep": "9", "cdPolEl": None}
    assert codes(check(a, [], defs, REFS)) == [
        ("AR-001", "cdART", "required"), ("AR-001", "cdConjRep", "not_in_table"),
        ("AR-001", "cdUnidPesoArt", "inactive_in_table"), ("AR-001", "cdUsumExtrArt", "required"),
    ]
    # cdCtrlUniArt only when snCtrlUniArt = S (AR-004 says it too).
    assert ("AR-001", "cdCtrlUniArt", "required_if") in codes(check({**good(), "snCtrlUniArt": "S"}, [], defs, REFS))
    # A S/N field's table is not its values: snCtrlVidaArt = S is no D114 code.
    assert not [f for f in check({**good(), "snCtrlVidaArt": "S"}, [LifeControl("01", Decimal(5))], defs, REFS) if f["code"] == "AR-001"]


@pytest.mark.parametrize(
    "levels, found",
    [
        (("N", "N", "N", "N"), [("AR-002", "snMtN1Art", "no_level")]),
        (("N", "S", "N", "S"), [("AR-002", "snMtN3Art", "gap")]),
        (("N", "S", "S", "S"), []),
        (("S", "S", "S", "S"), []),
    ],
)
def test_ar_002_repairable_levels(defs, levels, found):
    a = {**good(), "snRepaArt": "S", **dict(zip(("snMtN1Art", "snMtN2Art", "snMtN3Art", "snMtN4Art"), levels, strict=True))}
    assert codes(check(a, [], defs, REFS)) == found


def test_ar_002_only_for_a_repairable_one(defs):
    assert check({**good(), "snRepaArt": "N"}, [], defs, REFS) == []


def test_ar_003_measures_need_their_unit(defs):
    a = {**good(), "cdUnidPesoArt": None, "caLargoArt": Decimal(10), "caVoluArt": Decimal(5), "cdUnidVoluArt": "LI"}
    assert codes(check(a, [], defs, REFS)) == [("AR-003", "cdUnidLongArt", "unit_missing"), ("AR-003", "cdUnidPesoArt", "unit_missing")]
    assert check({**a, "cdUnidPesoArt": "KG", "cdUnidLongArt": "CM"}, [], defs, REFS) == []


def test_ar_004_unit_control_needs_its_code(defs):
    assert ("AR-004", "cdCtrlUniArt", "code_missing") in codes(check({**good(), "snCtrlUniArt": "S"}, [], defs, REFS))
    assert check({**good(), "snCtrlUniArt": "S", "cdCtrlUniArt": "S"}, [], defs, REFS) == []


def test_ar_005_life_control_pairs(defs):
    on = {**good(), "snCtrlVidaArt": "S"}
    assert ("AR-005", "cdUniVidaA", "no_pair") in codes(check(on, [], defs, REFS))
    assert ("AR-005", "caVidaArt", "pair_incomplete") in codes(check(on, [LifeControl("01", None)], defs, REFS))
    assert ("AR-005", "cdUniVidaA", "not_in_table") in codes(check(on, [LifeControl("01", 5), LifeControl("77", 2)], defs, REFS))
    assert check(on, [LifeControl("01", Decimal(5)), LifeControl("03", Decimal(2))], defs, REFS) == []


def test_ar_006_preventive_needs_life_control(defs):
    assert codes(check({**good(), "snMtPreArt": "S"}, [], defs, REFS)) == [("AR-006", "snCtrlVidaArt", "requires")]
    assert check({**good(), "snMtPreArt": "S", "snCtrlVidaArt": "S"}, [LifeControl("01", Decimal(1))], defs, REFS) == []


def test_ar_007_configuration_control(defs):
    a = {**good(), "snCnfgArt": "S"}
    assert codes(check(a, [], defs, REFS)) == [("AR-007", "cdConjRep", "group"), ("AR-007", "snCtrlUniArt", "unit_control")]
    for group in ("0", "7"):
        assert check({**a, "cdConjRep": group, "snCtrlUniArt": "S", "cdCtrlUniArt": "S"}, [], defs, REFS) == []


def test_ar_008_corrects_an_empty_security_code():
    a = {**good(), "cdSegArt": None}
    assert autocorrect(a) == [{"code": "AR-008", "field": "cdSegArt", "value": "U"}] and a["cdSegArt"] == "U"
    assert autocorrect(good()) == []
