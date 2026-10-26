"""The AR rules of an article (E12, plan §6): AR-001…AR-008.

Each rule is declared once (`RULES`): its code, severity, the MAR06 guide
fields it refers to and its parameters; the fields are named by their
PRISMA code, never by a column. `check()` runs them over an article's data
(PRISMA code -> value, plus its life controls) and returns its findings,
each with the field a person should look at. `autocorrect()` applies
AR-008 (an empty security code becomes "U"): a correction that is
recorded, not a finding.

Severities: AR-001 and AR-007 warn (AR-001 will block the SIGLE package,
phase 1b); AR-002…AR-006 are blocking; AR-008 corrects.

The texts live in the frontend (es.json, `articles.rules.<code>` and
`articles.findings.<problem>`): a finding carries only codes and params.
"""

from dataclasses import dataclass, field
from typing import Any

from app.services.article_fields import FieldDef

YES = "S"
WARNING, BLOCKING, CORRECTION = "aviso", "bloqueante", "autocorreccion"
LEVELS = ("snMtN1Art", "snMtN2Art", "snMtN3Art", "snMtN4Art")


@dataclass(frozen=True)
class Rule:
    code: str
    severity: str
    guide_fields: tuple[str, ...]
    params: dict[str, Any] = field(default_factory=dict)


RULES: dict[str, Rule] = {
    r.code: r
    for r in (
        # Basic data: the "Obligatorio" fields (some only when another one
        # says S), and the codes of their reference tables.
        Rule("AR-001", WARNING, ("1", "9", "15", "18", "19", "25", "26", "37", "53", "57", "58", "59", "60", "63", "64", "65"), {
            "conditional": {"cdCtrlUniArt": ["snCtrlUniArt", YES], "cdUniVidaA": ["snCtrlVidaArt", YES], "caVidaArt": ["snCtrlVidaArt", YES]},
            # Required for functional products (E14), not for every article.
            "optional": ["cdPolEl"],
            # Codes whose table AR-005 checks (every life control pair).
            "table_checked_by_other_rule": ["cdUniVidaA"],
        }),
        # Repairable: at least one maintenance level, and every level after the first.
        Rule("AR-002", BLOCKING, ("25", "58"), {"flag": "snRepaArt", "levels": list(LEVELS)}),
        Rule("AR-003", BLOCKING, ("40", "41", "42", "43", "44", "45", "46", "47"), {
            "units": {"caPesoArt": "cdUnidPesoArt", "caLargoArt": "cdUnidLongArt", "caAnchoArt": "cdUnidLongArt", "caAltoArt": "cdUnidLongArt", "caVoluArt": "cdUnidVoluArt"},
        }),
        Rule("AR-004", BLOCKING, ("59", "60"), {"flag": "snCtrlUniArt", "code": "cdCtrlUniArt"}),
        Rule("AR-005", BLOCKING, ("63", "64", "65"), {"flag": "snCtrlVidaArt", "table": "D114", "min": 1, "max": 3}),
        Rule("AR-006", BLOCKING, ("53", "63"), {"flag": "snMtPreArt", "requires": "snCtrlVidaArt"}),
        Rule("AR-007", WARNING, ("57", "59", "15"), {"flag": "snCnfgArt", "unit_control": "snCtrlUniArt", "group": "cdConjRep", "groups": ["0", "7"]}),
        Rule("AR-008", CORRECTION, ("19",), {"field": "cdSegArt", "default": "U"}),
    )
}


@dataclass(frozen=True)
class LifeControl:
    unit_code: str | None
    quantity: Any


def _finding(code: str, field_: str, problem: str, **params: Any) -> dict[str, Any]:
    rule = RULES[code]
    return {"code": code, "severity": rule.severity, "field": field_, "problem": problem, "params": params}


def _empty(value: Any) -> bool:
    return value is None or value == ""


def autocorrect(data: dict[str, Any]) -> list[dict[str, Any]]:
    """AR-008 on `data` (changed in place): the corrections made."""
    p = RULES["AR-008"].params
    if _empty(data.get(p["field"])):
        data[p["field"]] = p["default"]
        return [{"code": "AR-008", "field": p["field"], "value": p["default"]}]
    return []


def check(
    data: dict[str, Any], life: list[LifeControl], defs: dict[str, FieldDef], references: dict[str, dict[str, bool]]
) -> list[dict[str, Any]]:
    """Every AR finding of an article. `references`: table -> code -> active."""
    found: list[dict[str, Any]] = []
    first = life[0] if life else None
    values = {**data, "cdUniVidaA": first.unit_code if first else None, "caVidaArt": first.quantity if first else None}

    # AR-001: required fields and reference codes, from the definitions.
    p1 = RULES["AR-001"].params
    for prisma, d in defs.items():
        value = values.get(prisma)
        if prisma in p1["optional"]:
            pass
        elif prisma in p1["conditional"]:
            flag, wanted = p1["conditional"][prisma]
            if values.get(flag) == wanted and _empty(value):
                found.append(_finding("AR-001", prisma, "required_if", flag=flag))
        elif d.importance == "Obligatorio" and _empty(value):
            found.append(_finding("AR-001", prisma, "required"))
        # A S/N field's table is the related one (snCtrlVidaArt -> D114), not its values.
        if d.table and not d.allowed_values and not _empty(value) and prisma not in p1["table_checked_by_other_rule"]:
            state = references.get(d.table, {}).get(str(value))
            if state is None:
                found.append(_finding("AR-001", prisma, "not_in_table", table=d.table, value=str(value)))
            elif not state:
                found.append(_finding("AR-001", prisma, "inactive_in_table", table=d.table, value=str(value)))

    # AR-002
    p2 = RULES["AR-002"].params
    if values.get(p2["flag"]) == YES:
        marks = [values.get(level) == YES for level in p2["levels"]]
        if not any(marks):
            found.append(_finding("AR-002", p2["levels"][0], "no_level"))
        else:
            start = marks.index(True)
            missing = [p2["levels"][i] for i in range(start, len(marks)) if not marks[i]]
            if missing:
                found.append(_finding("AR-002", missing[0], "gap", levels=", ".join(missing)))

    # AR-003
    for measure, unit in RULES["AR-003"].params["units"].items():
        if not _empty(values.get(measure)) and _empty(values.get(unit)):
            found.append(_finding("AR-003", unit, "unit_missing", measure=measure))

    # AR-004
    p4 = RULES["AR-004"].params
    if values.get(p4["flag"]) == YES and _empty(values.get(p4["code"])):
        found.append(_finding("AR-004", p4["code"], "code_missing"))

    # AR-005
    p5 = RULES["AR-005"].params
    pairs = [c for c in life if not (_empty(c.unit_code) and _empty(c.quantity))]
    if values.get(p5["flag"]) == YES:
        if not pairs:
            found.append(_finding("AR-005", "cdUniVidaA", "no_pair"))
        for position, c in enumerate(life, start=1):
            if _empty(c.unit_code) and _empty(c.quantity):
                continue
            if _empty(c.unit_code) or _empty(c.quantity):
                found.append(_finding("AR-005", "cdUniVidaA" if _empty(c.unit_code) else "caVidaArt", "pair_incomplete", position=position))
            elif references.get(p5["table"], {}).get(str(c.unit_code)) is None:
                found.append(_finding("AR-005", "cdUniVidaA", "not_in_table", table=p5["table"], value=str(c.unit_code), position=position))
        if len(pairs) > p5["max"]:
            found.append(_finding("AR-005", "cdUniVidaA", "too_many", max=p5["max"]))

    # AR-006
    p6 = RULES["AR-006"].params
    if values.get(p6["flag"]) == YES and values.get(p6["requires"]) != YES:
        found.append(_finding("AR-006", p6["requires"], "requires", flag=p6["flag"]))

    # AR-007
    p7 = RULES["AR-007"].params
    if values.get(p7["flag"]) == YES:
        if values.get(p7["unit_control"]) != YES:
            found.append(_finding("AR-007", p7["unit_control"], "unit_control"))
        if values.get(p7["group"]) not in p7["groups"]:
            found.append(_finding("AR-007", p7["group"], "group", groups=", ".join(p7["groups"]), value=values.get(p7["group"]) or ""))
    return found
