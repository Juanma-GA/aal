"""The NT 10/17 validator (E16, RF-03): one engine, one list of codes.

A rule is a function registered under its code (`@rule("CF-001")`), with
its scope, severity and reference in app/validacion/catalog.py. Its check
is pure: it reads a `Context` -- a snapshot of one CUF's CONFUNFIS (rows,
their articles and references, the parts of those articles, the
functional products, the extra functions and incompatibilities) and the
values it is checked against (the CUF's normalized configuration, the
`confunfis` parameter, the active codes of the reference tables) -- and
yields `Finding`s. The snapshot holds whatever has the attributes: the ORM
objects of a stored CUF (app/services/validation.py) or the rows an import
would leave (app/services/anexo_xi_import.py, which so analyses without
writing). Nothing here touches the database.

`run()` gives every finding of every rule; which ones count, and how
(blocking, warning, off), is the rules' configuration
(`validation_rule`), applied by whoever reads them.
"""

import re
from collections import defaultdict
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from app.services.catalog import SNS_RE
from app.services.confunfis_graph import ROOT, Graph, Row, key_text
from app.validacion.catalog import ARTICLE, BY_CODE, CUF, EXTRA, INCOMPATIBILITY, PART, PRODUCT, ROW

_TWO_DIGITS = re.compile(r"^\d{2}$")
# A link note of a row or a part: its P/N + NCAGE is another article's (E13 OF-011, E14 OP-007).
_PN_TAKEN = {"OF-011", "OP-007", "pn_taken"}


@dataclass(frozen=True)
class Finding:
    code: str
    entity_type: str
    entity_id: str
    problem: str
    params: dict[str, Any] = field(default_factory=dict)
    # The field a person should look at, and the CONFUNFIS row to open ("Ir a").
    field: str | None = None
    row_id: str | None = None

    def as_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {"code": self.code, "problem": self.problem, "params": self.params}
        if self.field:
            out["field"] = self.field
        return out


@dataclass
class Context:
    rows: list[Any]
    config: set[str]
    params: dict[str, Any]
    articles: dict[Any, Any] = field(default_factory=dict)
    references: dict[Any, Any] = field(default_factory=dict)
    # Article id -> its AR findings (E12: as stored on the article, or computed for one an import would create).
    article_findings: dict[Any, list[dict[str, Any]]] = field(default_factory=dict)
    # Article id -> its data by PRISMA code (CF-019 reads the unit control).
    article_data: dict[Any, dict[str, Any]] = field(default_factory=dict)
    products: list[Any] = field(default_factory=list)
    parts: list[Any] = field(default_factory=list)
    # Every part of the master (parent article -> part articles): a cycle may cross any breakdown.
    part_edges: dict[Any, set[Any]] = field(default_factory=dict)
    extras: list[Any] = field(default_factory=list)
    incompatibilities: list[Any] = field(default_factory=list)
    # Reference table -> its active codes (POL, NAE, D155, UNIDAD_MEDIDA_PF).
    codes: dict[str, set[str]] = field(default_factory=dict)
    # The SNS where this CUF sits as a mounted CUF in another one (CF-009).
    mounted_sns: set[str] = field(default_factory=set)
    # The CUF data of every row of a file, by field (CF-016: an import only).
    file_cuf: dict[str, list[str]] | None = None
    # Whether a part's article also sits in a CONFUNFIS with its parent (TP-001):
    # by default, in this CUF.
    part_in_confunfis: Callable[[Any], bool] | None = None
    graph: Graph = field(init=False)

    def __post_init__(self) -> None:
        self.graph = Graph(graph_row(r) for r in self.rows)
        self.by_id = {str(r.id): r for r in self.rows}
        self.cuf_articles = {r.article_id for r in self.rows if r.article_id}


def graph_row(r: Any) -> Row:
    return Row(str(r.id), r.sns, r.co, r.al, r.qty, r.cs_sns, r.cs_co, r.cs_al)


Check = Callable[[Context, dict[str, Any]], Iterable[Finding]]
RULES: dict[str, Check] = {}


def rule(code: str) -> Callable[[Check], Check]:
    if code not in BY_CODE:
        raise ValueError(f"{code} is not in the rules' catalog")

    def register(check: Check) -> Check:
        RULES[code] = check
        return check

    return register


def run(ctx: Context, params: dict[str, dict[str, Any]] | None = None) -> list[Finding]:
    """Every finding of every registered rule (each with its catalog
    parameters, over-ridden by `params`: code -> parameters)."""
    out: list[Finding] = []
    for code, check in RULES.items():
        out += list(check(ctx, {**BY_CODE[code].params, **((params or {}).get(code) or {})}))
    return out


# ── helpers ──────────────────────────────────────────────────────────────


def _blank(value: Any) -> bool:
    return value is None or not str(value).strip()


def _cs_text(r: Any) -> str:
    return " ".join(x or "" for x in (r.cs_sns, r.cs_co, r.cs_al)).strip()


def _row(r: Any, code: str, problem: str, field_: str | None = None, **params: Any) -> Finding:
    return Finding(code, ROW, str(r.id), problem, params, field_, str(r.id))


def _out_of(value: str | None, bounds: dict[str, int]) -> bool:
    return not _TWO_DIGITS.match(value or "") or not bounds["min"] <= int(value) <= bounds["max"]


def _is_root(r: Any) -> bool:
    return (r.sns, r.co, r.al) == ROOT


def _principal_rows(ctx: Context) -> list[Any]:
    """The CUF's own row: at 000000 01 00, or (a mounted CUF) at the SNS of its function, with no CS."""
    roots = [r for r in ctx.rows if _is_root(r)]
    if roots:
        return roots
    return [r for r in ctx.rows if r.sns in ctx.mounted_sns and _blank(r.cs_sns) and _blank(r.cs_co) and _blank(r.cs_al)]


def _ordered(rows: Iterable[Any]) -> list[Any]:
    """In the order they were created (E15: clock_timestamp), the first of a duplicate first."""
    return sorted(rows, key=lambda r: (str(getattr(r, "created_at", "") or ""), str(r.id)))


def cycles(edges: dict[Any, set[Any]]) -> set[tuple[Any, Any]]:
    """The edges on a cycle (Tarjan's strongly connected components, iterative)."""
    index: dict[Any, int] = {}
    low: dict[Any, int] = {}
    on_stack: set[Any] = set()
    stack: list[Any] = []
    component_of: dict[Any, int] = {}
    counter = 0
    components = 0
    for start in list(edges):
        if start in index:
            continue
        work = [(start, iter(sorted(edges.get(start, ()), key=str)))]
        index[start] = low[start] = counter
        counter += 1
        stack.append(start)
        on_stack.add(start)
        while work:
            node, it = work[-1]
            advanced = False
            for nxt in it:
                if nxt not in index:
                    index[nxt] = low[nxt] = counter
                    counter += 1
                    stack.append(nxt)
                    on_stack.add(nxt)
                    work.append((nxt, iter(sorted(edges.get(nxt, ()), key=str))))
                    advanced = True
                    break
                if nxt in on_stack:
                    low[node] = min(low[node], index[nxt])
            if advanced:
                continue
            work.pop()
            if work:
                low[work[-1][0]] = min(low[work[-1][0]], low[node])
            if low[node] == index[node]:
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    component_of[member] = components
                    if member == node:
                        break
                components += 1
    return {(a, b) for a, targets in edges.items() for b in targets if a == b or (a in component_of and component_of.get(a) == component_of.get(b))}


# ── CONFUNFIS rows (§9.1) ────────────────────────────────────────────────


@rule("CF-001")
def _cf001(ctx: Context, p: dict[str, Any]) -> Iterator[Finding]:
    for r in ctx.rows:
        if not _is_root(r) and r.sns and SNS_RE.match(r.sns) and r.sns not in ctx.config:
            yield _row(r, "CF-001", "outside", "sns", sns=r.sns)


@rule("CF-002")
def _cf002(ctx: Context, p: dict[str, Any]) -> Iterator[Finding]:
    for r in ctx.rows:
        if not r.sns or not SNS_RE.match(r.sns):
            yield _row(r, "CF-002", "sns", "sns", sns=r.sns or "")
        if ctx.graph.orphan.get(str(r.id)) == "malformed":
            yield _row(r, "CF-002", "cs", "cs", cs=_cs_text(r))


@rule("CF-003")
def _cf003(ctx: Context, p: dict[str, Any]) -> Iterator[Finding]:
    bounds = ctx.params["co"]
    for r in ctx.rows:
        if not _is_root(r) and _out_of(r.co, bounds):
            yield _row(r, "CF-003", "range", "co", co=r.co or "", min=f"{bounds['min']:02d}", max=f"{bounds['max']:02d}")


@rule("CF-004")
def _cf004(ctx: Context, p: dict[str, Any]) -> Iterator[Finding]:
    bounds = ctx.params["al"]
    g = ctx.graph
    for r in ctx.rows:
        if _is_root(r):
            continue
        if not _TWO_DIGITS.match(r.al or "") or (r.al != "00" and not bounds["min"] <= int(r.al) <= bounds["max"]):
            yield _row(r, "CF-004", "range", "al", al=r.al or "", max=f"{bounds['max']:02d}")
            continue
        als = {x.al for x in g.by_hueco[(r.sns, r.co)]}
        if r.al != "00" and len(als) == 1:
            yield _row(r, "CF-004", "alone", "al", al=r.al)
        elif "00" in als and len(als) > 1:
            yield _row(r, "CF-004", "mixed", "al", al=r.al)


@rule("CF-005")
def _cf005(ctx: Context, p: dict[str, Any]) -> Iterator[Finding]:
    top = Decimal(str(ctx.params["qty"]["max"]))
    for r in ctx.rows:
        qty = r.qty
        if qty is None:
            yield _row(r, "CF-005", "missing", "qty")
            continue
        try:
            qty = Decimal(str(qty))
        except InvalidOperation:
            yield _row(r, "CF-005", "not_whole", "qty", qty=str(r.qty))
            continue
        if qty <= 0:
            yield _row(r, "CF-005", "not_positive", "qty", qty=str(qty.normalize()))
        elif qty != qty.to_integral_value():
            yield _row(r, "CF-005", "not_whole", "qty", qty=str(qty.normalize()))
        elif qty > top:
            yield _row(r, "CF-005", "too_big", "qty", qty=str(qty.normalize()), max=str(top))


@rule("CF-006")
def _cf006(ctx: Context, p: dict[str, Any]) -> Iterator[Finding]:
    groups: dict[tuple, list[Any]] = defaultdict(list)
    for r in ctx.rows:
        parent = ctx.graph.parent.get(str(r.id))
        if parent is not None and not _is_root(r):
            groups[(r.sns, r.co, parent)].append(r)
    for (sns, co, _parent), rows in groups.items():
        qtys = {None if r.qty is None else Decimal(str(r.qty)).normalize() for r in rows}
        if len({x.al for x in rows}) > 1 and len(qtys) > 1:
            shown = ", ".join(sorted("—" if q is None else str(q) for q in qtys))
            for r in rows:
                yield _row(r, "CF-006", "different", "qty", qtys=shown)


@rule("CF-007")
def _cf007(ctx: Context, p: dict[str, Any]) -> Iterator[Finding]:
    for r in ctx.rows:
        if ctx.graph.orphan.get(str(r.id)) == "not_found":
            yield _row(r, "CF-007", "not_found", "cs", cs=_cs_text(r))


@rule("CF-008")
def _cf008(ctx: Context, p: dict[str, Any]) -> Iterator[Finding]:
    principal = {str(r.id) for r in _principal_rows(ctx)}
    for r in ctx.rows:
        if str(r.id) not in principal and not _is_root(r) and _blank(r.cs_sns) and _blank(r.cs_co) and _blank(r.cs_al):
            yield _row(r, "CF-008", "missing", "cs")


@rule("CF-009")
def _cf009(ctx: Context, p: dict[str, Any]) -> Iterator[Finding]:
    principal = _principal_rows(ctx)
    if not principal:
        yield Finding("CF-009", CUF, "cuf", "missing", {})
        return
    for r in _ordered(principal)[1:]:
        yield _row(r, "CF-009", "several", "sns", count=len(principal))
    for r in principal:
        if _is_root(r) and not (_blank(r.cs_sns) and _blank(r.cs_co) and _blank(r.cs_al)) and (r.cs_sns, r.cs_co, r.cs_al) != ROOT:
            yield _row(r, "CF-009", "with_cs", "cs", cs=_cs_text(r))


@rule("CF-010")
def _cf010(ctx: Context, p: dict[str, Any]) -> Iterator[Finding]:
    for r in ctx.rows:
        if ctx.graph.in_cycle(ctx.graph.rows[str(r.id)]):
            yield _row(r, "CF-010", "cycle", "cs")


def _identity(ctx: Context, r: Any) -> tuple[Any, Any]:
    article = ctx.articles.get(r.article_id) if r.article_id else None
    reference = ctx.references.get(r.article_reference_id) if r.article_reference_id else None
    return article, reference


@rule("CF-011")
def _cf011(ctx: Context, p: dict[str, Any]) -> Iterator[Finding]:
    g = ctx.graph
    for key, children in g.children.items():
        if key == ROOT and not g.by_key.get(ROOT):
            continue
        for r in g.by_key.get(key, []):
            article, reference = _identity(ctx, ctx.by_id[r.id])
            if (article is None or article.noc is None) and reference is None:
                yield _row(ctx.by_id[r.id], "CF-011", "no_identity", "noc", children=len(children))


@rule("CF-012")
def _cf012(ctx: Context, p: dict[str, Any]) -> Iterator[Finding]:
    for r in ctx.rows:
        article, reference = _identity(ctx, r)
        if any((n or {}).get("code") in _PN_TAKEN for n in r.link_notes or []):
            note = next(n for n in r.link_notes if n.get("code") in _PN_TAKEN)
            yield _row(r, "CF-012", "pn_taken", "pn", **(note.get("params") or {}))
        if article is not None and article.noc:
            continue
        if reference is None:
            yield _row(r, "CF-012", "no_identity", "noc")
        elif _blank(reference.ncage):
            yield _row(r, "CF-012", "pn_without_ncage", "ncage", pn=reference.pn)


@rule("CF-013")
def _cf013(ctx: Context, p: dict[str, Any]) -> Iterator[Finding]:
    for r in ctx.rows:
        _article, reference = _identity(ctx, r)
        if reference is not None and not _blank(reference.ncage) and len(str(reference.ncage).strip()) != 5:
            yield _row(r, "CF-013", "length", "ncage", ncage=reference.ncage)


@rule("CF-014")
def _cf014(ctx: Context, p: dict[str, Any]) -> Iterator[Finding]:
    for r in ctx.rows:
        if _blank(r.article_name):
            yield _row(r, "CF-014", "name", "article_name")
        if _blank(r.function_text):
            yield _row(r, "CF-014", "function", "function_text")


@rule("CF-015")
def _cf015(ctx: Context, p: dict[str, Any]) -> Iterator[Finding]:
    duplicated = ctx.graph.duplicates()
    seen: set[tuple] = set()
    for r in _ordered(x for x in ctx.rows if str(x.id) in duplicated):
        cs = ctx.graph.parent.get(str(r.id)) or (r.cs_sns, r.cs_co, r.cs_al)
        group = (r.sns, r.co, r.al, cs)
        if group in seen:
            yield _row(r, "CF-015", "duplicate", "sns", position=key_text((r.sns, r.co, r.al)))
        seen.add(group)


@rule("CF-016")
def _cf016(ctx: Context, p: dict[str, Any]) -> Iterator[Finding]:
    for name, values in (ctx.file_cuf or {}).items():
        if len(set(values)) > 1:
            yield Finding("CF-016", CUF, "cuf", "different", {"field": name, "values": ", ".join(sorted(set(values)))})


@rule("CF-017")
def _cf017(ctx: Context, p: dict[str, Any]) -> Iterator[Finding]:
    by_article: dict[Any, list[Any]] = defaultdict(list)
    for r in ctx.rows:
        if r.article_id and not _is_root(r):
            by_article[r.article_id].append(r)
    for article_id, rows in by_article.items():
        sns = sorted({r.sns for r in rows})
        if len(sns) > 1:
            first = sorted(rows, key=lambda r: (r.sns, r.co, r.al))[0]
            article = ctx.articles.get(article_id)
            yield Finding(
                "CF-017", ARTICLE, str(article_id), "several_sns",
                {"positions": ", ".join(sns), "noc": getattr(article, "noc", None) or "", "name": getattr(article, "nombre", None) or first.article_name or ""},
                "sns", str(first.id),
            )


@rule("CF-018")
def _cf018(ctx: Context, p: dict[str, Any]) -> Iterator[Finding]:
    for r in ctx.rows:
        if _blank(r.ct_sigle):
            yield _row(r, "CF-018", "missing", "ct_sigle")


@rule("CF-019")
def _cf019(ctx: Context, p: dict[str, Any]) -> Iterator[Finding]:
    for r in ctx.rows:
        if r.ct_sigle == "S" and r.article_id and (ctx.article_data.get(r.article_id) or {}).get(p["field"]) == "N":
            yield _row(r, "CF-019", "no_unit_control", "ct_sigle")


@rule("CF-020")
def _cf020(ctx: Context, p: dict[str, Any]) -> Iterator[Finding]:
    for e in ctx.extras:
        row = ctx.by_id.get(str(e.position_id))
        if row is not None and e.sns == row.sns:
            yield Finding("CF-020", EXTRA, str(e.id), "same_sns", {"sns": e.sns}, "sns", str(e.position_id))
        elif e.sns not in ctx.config:
            yield Finding("CF-020", EXTRA, str(e.id), "outside", {"sns": e.sns}, "sns", str(e.position_id))


@rule("CF-021")
def _cf021(ctx: Context, p: dict[str, Any]) -> Iterator[Finding]:
    g = ctx.graph
    requires: dict[Any, set[Any]] = defaultdict(set)
    for i in ctx.incompatibilities:
        if i.kind == "requiere":
            requires[str(i.row_a_id)].add(str(i.row_b_id))
    cyclic = cycles(requires)
    for i in ctx.incompatibilities:
        a, b = g.rows.get(str(i.row_a_id)), g.rows.get(str(i.row_b_id))
        if i.kind == "excluye" and a and b and not g.is_alternative(a) and not g.is_alternative(b):
            yield Finding("CF-021", INCOMPATIBILITY, str(i.id), "excluye_without_alternatives", {}, None, str(i.row_a_id))
        if i.kind == "requiere" and b is None:
            yield Finding("CF-021", INCOMPATIBILITY, str(i.id), "requiere_removed", {}, None, str(i.row_a_id))
        if i.kind == "requiere" and (str(i.row_a_id), str(i.row_b_id)) in cyclic:
            yield Finding("CF-021", INCOMPATIBILITY, str(i.id), "requiere_cycle", {}, None, str(i.row_a_id))


# ── parts and functional products (§9.1.10, §9.1.11) ─────────────────────


def part_problems(ctx: Context) -> Iterator[Finding]:
    bounds_cop, bounds_alp = ctx.params["cop"], ctx.params["alp"]
    cyclic = cycles(ctx.part_edges)
    keys: dict[tuple, int] = defaultdict(int)
    alps: dict[tuple, set[str]] = defaultdict(set)
    for x in ctx.parts:
        keys[(x.parent_article_id, x.cop, x.alp)] += 1
        alps[(x.parent_article_id, x.cop)].add(x.alp)
    in_confunfis = ctx.part_in_confunfis or (lambda x: x.part_article_id in ctx.cuf_articles and x.parent_article_id in ctx.cuf_articles)
    row_of = {}
    for r in ctx.rows:
        if r.article_id:
            row_of.setdefault(r.article_id, str(r.id))
    for x in ctx.parts:
        def found(problem: str, field_: str | None = None, **params: Any) -> Finding:
            return Finding("TP-001", PART, str(x.id), problem, params, field_, row_of.get(x.parent_article_id))

        if x.part_article_id is not None and x.part_article_id == x.parent_article_id:
            yield found("self", "noc")
        elif x.part_article_id is not None and (x.parent_article_id, x.part_article_id) in cyclic:
            yield found("cycle", "noc")
        if _out_of(x.cop, bounds_cop):
            yield found("cop", "cop", cop=x.cop or "")
        if not _TWO_DIGITS.match(x.alp or "") or (x.alp != "00" and not bounds_alp["min"] <= int(x.alp) <= bounds_alp["max"]):
            yield found("alp", "alp", alp=x.alp or "")
        if keys[(x.parent_article_id, x.cop, x.alp)] > 1:
            yield found("duplicate", "cop", cop=x.cop, alp=x.alp)
        if x.quantity is None or Decimal(str(x.quantity)) <= 0:
            yield found("quantity", "quantity", quantity="" if x.quantity is None else str(Decimal(str(x.quantity)).normalize()))
        if x.alp != "00" and len(alps[(x.parent_article_id, x.cop)]) == 1:
            yield found("alone", "alp", alp=x.alp)
        if x.part_article_id is not None and in_confunfis(x):
            yield found("in_confunfis", "noc")
        if any((n or {}).get("code") in _PN_TAKEN for n in x.link_notes or []):
            note = next(n for n in x.link_notes if n.get("code") in _PN_TAKEN)
            yield found("pn_taken", "pn", **(note.get("params") or {}))


@rule("TP-001")
def _tp001(ctx: Context, p: dict[str, Any]) -> Iterator[Finding]:
    yield from part_problems(ctx)


def _plain(value: Any) -> Any:
    if isinstance(value, Decimal | int | float):
        return Decimal(str(value)).normalize()
    return (str(value).strip().upper() or None) if value is not None else None


@rule("PF-001")
def _pf001(ctx: Context, p: dict[str, Any]) -> Iterator[Finding]:
    same: dict[tuple, int] = defaultdict(int)
    fields = ("designation", "pol_code", "nae", "noc", "supply_unit", "quantity", "unit")
    for x in ctx.products:
        same[tuple(_plain(getattr(x, f)) for f in fields)] += 1
    for x in ctx.products:
        def found(problem: str, field_: str, **params: Any) -> Finding:
            return Finding("PF-001", PRODUCT, str(x.id), problem, params, field_)

        if x.pol_code and x.pol_code not in ctx.codes.get("POL", set()):
            yield found("pol", "pol_code", pol=x.pol_code)
        if x.nae and x.nae not in ctx.codes.get("NAE", set()):
            yield found("nae", "nae", nae=x.nae)
        if x.supply_unit and x.supply_unit not in ctx.codes.get("D155", set()):
            yield found("supply_unit", "supply_unit", unit=x.supply_unit)
        if x.unit and x.unit not in ctx.codes.get("UNIDAD_MEDIDA_PF", set()):
            yield found("unit", "unit", unit=x.unit)
        if x.quantity is not None and Decimal(str(x.quantity)) <= 0:
            yield found("quantity", "quantity", quantity=str(Decimal(str(x.quantity)).normalize()))
        if same[tuple(_plain(getattr(x, f)) for f in fields)] > 1:
            yield found("duplicate", "designation")


# ── the articles' AR rules (E12, MAR06) ──────────────────────────────────


def _ar(code: str) -> Check:
    def check(ctx: Context, p: dict[str, Any]) -> Iterator[Finding]:
        row_of: dict[Any, str] = {}
        for r in ctx.rows:
            if r.article_id:
                row_of.setdefault(r.article_id, str(r.id))
        for article_id, findings in ctx.article_findings.items():
            for f in findings:
                if f.get("code") == code:
                    yield Finding(code, ARTICLE, str(article_id), f.get("problem") or "", f.get("params") or {}, f.get("field"), row_of.get(article_id))

    return check


for _code in ("AR-001", "AR-002", "AR-003", "AR-004", "AR-005", "AR-006", "AR-007"):
    rule(_code)(_ar(_code))
