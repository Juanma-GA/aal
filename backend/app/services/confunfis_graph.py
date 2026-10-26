"""The CONFUNFIS as a graph (E13, NT §9.1.7-9.1.8), computed from its rows
and never stored. Pure: no database, so the cases of the norm are tested
as they are.

- A position is SNS + CO + AL; a hueco is SNS + CO (its alternatives, AL,
  share CO and QTY). The CUF itself is `000000 01 00` (ROOT): a row there
  is the CUF, with no higher assembly.
- A row's CS is the SNS + CO + AL of another row. Empty, it is the CUF. It
  is *malformed* when a part does not have its format (an SNS of six
  letters or digits, a CO and an AL of two digits), *not found* when no row
  has that position (the CUF always exists, row or not); either way the
  row is an orphan.
- The structure is a graph, not a tree: the same component may hang from
  several CS (§9.1.8 case 2: the computer in the 10U or the 12U cabinet,
  alternatives of each other), and the same NOC may sit in two huecos with
  different CS (case 1, the switch).
- Total in the CUF of a hueco = its QTY × the sum of the totals of the
  distinct huecos its rows hang from. Alternative CS (positions of one
  hueco) count once, and so do the AL: the laser with 3 AL × 2 alternative
  CS is 1, not 6. A hueco on a cycle, or hanging from one, has no total.
"""

import re
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from app.services.catalog import SNS_RE

Key = tuple[str, str, str]
Hueco = tuple[str, str]

ROOT: Key = ("000000", "01", "00")
ROOT_HUECO: Hueco = ROOT[:2]
_TWO_DIGITS = re.compile(r"^\d{2}$")
# The paths a calculation shows at most (a component in many huecos).
MAX_CHAINS = 20


@dataclass(frozen=True)
class Row:
    id: str
    sns: str
    co: str
    al: str
    qty: Decimal | None
    cs_sns: str | None = None
    cs_co: str | None = None
    cs_al: str | None = None

    @property
    def key(self) -> Key:
        return (self.sns, self.co, self.al)

    @property
    def hueco(self) -> Hueco:
        return (self.sns, self.co)


def _blank(value: str | None) -> bool:
    return value is None or not str(value).strip()


def key_text(key: Key) -> str:
    return " ".join(key)


def well_formed(sns: str | None, co: str | None, al: str | None) -> bool:
    return bool(sns and SNS_RE.match(sns) and co and _TWO_DIGITS.match(co) and al and _TWO_DIGITS.match(al))


class Graph:
    def __init__(self, rows: Iterable[Row]):
        self.rows: dict[str, Row] = {r.id: r for r in rows}
        self.by_key: dict[Key, list[Row]] = defaultdict(list)
        self.by_hueco: dict[Hueco, list[Row]] = defaultdict(list)
        for r in self.rows.values():
            self.by_key[r.key].append(r)
            self.by_hueco[r.hueco].append(r)
        # row id -> its CS key ("root" rows: None), and the orphans' reason.
        self.parent: dict[str, Key | None] = {}
        self.orphan: dict[str, str] = {}
        for r in self.rows.values():
            self._resolve(r)
        self.children: dict[Key, list[Row]] = defaultdict(list)
        for rid, key in self.parent.items():
            if key is not None:
                self.children[key].append(self.rows[rid])
        self.cycle_huecos = self._cycles()
        self._totals: dict[Hueco, Decimal | None] = {}

    def _resolve(self, r: Row) -> None:
        if r.key == ROOT:
            self.parent[r.id] = None
            return
        if _blank(r.cs_sns) and _blank(r.cs_co) and _blank(r.cs_al):
            self.parent[r.id] = ROOT
            return
        if not well_formed(r.cs_sns, r.cs_co, r.cs_al):
            self.orphan[r.id] = "malformed"
            return
        key = (str(r.cs_sns), str(r.cs_co), str(r.cs_al))
        if key != ROOT and key not in self.by_key:
            self.orphan[r.id] = "not_found"
            return
        self.parent[r.id] = key

    # ── huecos and their CS ──────────────────────────────────────────────

    def cs_huecos(self, hueco: Hueco) -> list[Hueco]:
        """The distinct huecos the rows of `hueco` hang from."""
        out = {self.parent[r.id][:2] for r in self.by_hueco.get(hueco, []) if self.parent.get(r.id) is not None}  # type: ignore[index]
        return sorted(out)

    def _cycles(self) -> set[Hueco]:
        """Huecos on a cycle (Tarjan's strongly connected components)."""
        index: dict[Hueco, int] = {}
        low: dict[Hueco, int] = {}
        on_stack: set[Hueco] = set()
        stack: list[Hueco] = []
        found: set[Hueco] = set()
        counter = 0
        for start in list(self.by_hueco):
            if start in index:
                continue
            work = [(start, iter(self.cs_huecos(start)))]
            index[start] = low[start] = counter
            counter += 1
            stack.append(start)
            on_stack.add(start)
            while work:
                node, edges = work[-1]
                advanced = False
                for nxt in edges:
                    if nxt not in self.by_hueco:
                        continue  # the virtual CUF
                    if nxt not in index:
                        index[nxt] = low[nxt] = counter
                        counter += 1
                        stack.append(nxt)
                        on_stack.add(nxt)
                        work.append((nxt, iter(self.cs_huecos(nxt))))
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
                    component = []
                    while True:
                        member = stack.pop()
                        on_stack.discard(member)
                        component.append(member)
                        if member == node:
                            break
                    if len(component) > 1 or node in self.cs_huecos(node):
                        found.update(component)
        return found

    def qty(self, hueco: Hueco) -> Decimal | None:
        values = [r.qty for r in self.by_hueco.get(hueco, []) if r.qty is not None]
        return max(values) if values else None

    def total(self, hueco: Hueco) -> Decimal | None:
        """Units of the hueco in one CUF (None: an orphan, a cycle, no QTY)."""
        if hueco == ROOT_HUECO:
            return Decimal(1)
        if hueco in self._totals:
            return self._totals[hueco]
        self._totals[hueco] = None  # guards a cycle the detection missed
        result: Decimal | None = None
        qty = self.qty(hueco)
        parents = self.cs_huecos(hueco)
        if hueco not in self.cycle_huecos and qty is not None and parents:
            parts = [self.total(p) for p in parents]
            if all(p is not None for p in parts):
                result = qty * sum(parts, Decimal(0))  # type: ignore[arg-type]
        self._totals[hueco] = result
        return result

    def chains(self, hueco: Hueco) -> list[list[tuple[Decimal | None, str | None]]]:
        """How the total comes out: one path per CS hueco up to the CUF, each
        a list of (QTY, SNS), the first one the hueco's own (SNS None).
        "3 × 6 (A21030) × 1 (A20000) = 18"."""
        out: list[list[tuple[Decimal | None, str | None]]] = []

        def walk(h: Hueco, path: list[tuple[Decimal | None, str | None]], seen: set[Hueco]) -> None:
            if len(out) >= MAX_CHAINS:
                return
            parents = self.cs_huecos(h)
            if not parents or h in seen:
                out.append(path)
                return
            for p in parents:
                if p == ROOT_HUECO:
                    out.append(path)
                else:
                    walk(p, [*path, (self.qty(p), p[0])], seen | {h})

        if hueco != ROOT_HUECO:
            walk(hueco, [(self.qty(hueco), None)], set())
        return out

    # ── row flags ────────────────────────────────────────────────────────

    def is_alternative(self, r: Row) -> bool:
        """An AL of a hueco with alternatives."""
        return r.al != "00" or len({x.al for x in self.by_hueco[r.hueco]}) > 1

    def is_cs_alternative(self, r: Row) -> bool:
        """The same position under several CS (§9.1.8 case 2)."""
        return len({(x.cs_sns, x.cs_co, x.cs_al) for x in self.by_key[r.key]}) > 1

    def duplicates(self) -> set[str]:
        """Rows identical in SNS + CO + AL + CS to another."""
        groups: dict[tuple, list[str]] = defaultdict(list)
        for r in self.rows.values():
            groups[(*r.key, r.cs_sns, r.cs_co, r.cs_al)].append(r.id)
        return {rid for ids in groups.values() if len(ids) > 1 for rid in ids}

    def in_cycle(self, r: Row) -> bool:
        return r.hueco in self.cycle_huecos
