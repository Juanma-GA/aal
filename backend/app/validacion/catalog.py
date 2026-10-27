"""The catalog of the NT 10/17 rules (E16, plan §6): one entry per rule, the
single source of its code, scope, default severity, NT reference and
parameters. Migration 0016 seeds `validation_rule` from it (the admin then
changes the activation, severity, parameters and help text there); the
engine (app/validacion/engine.py) registers each rule's check under the
same code. The texts a person reads live in the frontend (es.json,
`validation.rules.<code>` and `validation.problems.<code>.<problem>`).

Severities: "bloqueante" blocks the delivery; "aviso" does not (and can be
accepted with a justification); "desactivada" turns the rule off. The
ranges and limits a rule checks against (CO, AL, QTY, COP, ALP) are the
`confunfis` parameter, the one the forms use too: one source for both.
"""

from dataclasses import dataclass, field
from typing import Any

BLOCKING, WARNING, OFF = "bloqueante", "aviso", "desactivada"
SEVERITIES = (BLOCKING, WARNING, OFF)

# What a finding is about: a CONFUNFIS row, the CUF as a whole, an article,
# a part of an article's breakdown, a functional product, an extra function
# of a row, an incompatibility between rows.
ROW, CUF, ARTICLE, PART, PRODUCT, EXTRA, INCOMPATIBILITY = "fila", "cuf", "articulo", "parte", "producto", "funcion_adicional", "incompatibilidad"
SCOPES = (ROW, CUF, ARTICLE, PART, PRODUCT, EXTRA, INCOMPATIBILITY)


@dataclass(frozen=True)
class RuleInfo:
    code: str
    scope: str
    severity: str
    ref: str
    params: dict[str, Any] = field(default_factory=dict)


CATALOG: tuple[RuleInfo, ...] = (
    RuleInfo("CF-001", ROW, BLOCKING, "NT §8, §9.1.1"),
    RuleInfo("CF-002", ROW, BLOCKING, "NT §6"),
    RuleInfo("CF-003", ROW, BLOCKING, "NT §9.1.5"),
    RuleInfo("CF-004", ROW, BLOCKING, "NT §9.1.6"),
    RuleInfo("CF-005", ROW, BLOCKING, "NT §9.1.7"),
    RuleInfo("CF-006", ROW, BLOCKING, "NT §9.1.6–7"),
    RuleInfo("CF-007", ROW, BLOCKING, "NT §9.1.8"),
    RuleInfo("CF-008", ROW, BLOCKING, "NT §9.1.8"),
    RuleInfo("CF-009", CUF, BLOCKING, "NT §9.1.12"),
    RuleInfo("CF-010", ROW, BLOCKING, "NT §9.1.8"),
    RuleInfo("CF-011", ROW, WARNING, "NT §9.1.8"),
    RuleInfo("CF-012", ROW, BLOCKING, "NT §9.1.3"),
    RuleInfo("CF-013", ROW, BLOCKING, "NT §9.1.3"),
    RuleInfo("CF-014", ROW, BLOCKING, "DEL v02"),
    RuleInfo("CF-015", ROW, BLOCKING, "—"),
    RuleInfo("CF-016", CUF, BLOCKING, "NT §9"),
    RuleInfo("CF-017", ARTICLE, WARNING, "NT §9.1.1"),
    RuleInfo("CF-018", ROW, WARNING, "NT §9.1.9"),
    RuleInfo("CF-019", ROW, WARNING, "NT §9.1.9, MAR06 campo 59", {"field": "snCtrlUniArt"}),
    RuleInfo("CF-020", EXTRA, BLOCKING, "NT §9.1.1"),
    RuleInfo("CF-021", INCOMPATIBILITY, WARNING, "RF-02"),
    RuleInfo("TP-001", PART, BLOCKING, "NT §9.1.10"),
    RuleInfo("PF-001", PRODUCT, BLOCKING, "NT §9.1.11"),
    # The article rules of E12 (app/validacion/articulos.py), over the
    # articles of the CUF's rows and of their parts. AR-008 corrects
    # (an empty security code becomes U): it is never a finding.
    RuleInfo("AR-001", ARTICLE, WARNING, "MAR06"),
    RuleInfo("AR-002", ARTICLE, BLOCKING, "MAR06"),
    RuleInfo("AR-003", ARTICLE, BLOCKING, "MAR06"),
    RuleInfo("AR-004", ARTICLE, BLOCKING, "MAR06"),
    RuleInfo("AR-005", ARTICLE, BLOCKING, "MAR06"),
    RuleInfo("AR-006", ARTICLE, BLOCKING, "MAR06"),
    RuleInfo("AR-007", ARTICLE, WARNING, "MAR06"),
)
BY_CODE: dict[str, RuleInfo] = {r.code: r for r in CATALOG}
