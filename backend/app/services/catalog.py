"""The normalized functional configuration (E10, NT 10/17 §6-8, Anexo II),
without the database: from the rows of a CONF_FUN file to the catalog of
one version, with its warnings.

Level and parent come from the SNS code (NT §6, fig. 6-2, YY Y Y Y Y):
000000 or XX0000 SISTEMA (no parent), XXX000 SUBSISTEMA, XXXX00
SUBSUBSISTEMA, XXXXX0 CONJUNTO, anything else SUBCONJUNTO; the parent sets
the last significant position to 0. Letters are significant (L4121C is a
SUBCONJUNTO under L41210).

The warnings (none of them drops a row, HR7):
- CN-001: an SNS with more than one name in the same subcategory (an
  ELEMENTO row, which adds a name under a subconjunto, counts): one per SNS.
- CN-002: a row whose declared level is not the code's (ELEMENTO rows are
  not levels and are counted apart): one per row.
- CN-003: an SNS whose derived parent is not in the version: one per SNS.
- CN-004: a row without category nor subcategory: one per row. It is kept
  (its SNS is in the version) but has no place in any subcategory's tree,
  so CN-002 and CN-003 do not look at it.
- CN-005: a description split into a ninth column (an unescaped quote in
  the source): joined back with ", " (where the source split it) and the
  surrounding quotes removed; one per row.
- CN-006: a pending description (PTE, or starting with TBD): one per row.
- CN-007: the same SNS with different descriptions in different subcategories
  (NT §6: an SNS names one function); the values with their subcategory.
"""

import re
from dataclasses import dataclass, field
from typing import Any

SNS_RE = re.compile(r"^[A-Z0-9]{6}$")
TWO_DIGITS_RE = re.compile(r"^\d{2}$")
LEVELS = ("SISTEMA", "SUBSISTEMA", "SUBSUBSISTEMA", "CONJUNTO", "SUBCONJUNTO")
ELEMENTO = "ELEMENTO"
# Origin of an extra name seen only in another subcategory (not a CN-001).
OTHER_SUBCATEGORY = "OTRA_SUBCATEGORIA"
WARNING_CODES = ("cn_001", "cn_002", "cn_003", "cn_004", "cn_005", "cn_006", "cn_007")


def derived_level(sns: str) -> str:
    if sns[2:] == "0000":
        return "SISTEMA"
    if sns[3:] == "000":
        return "SUBSISTEMA"
    if sns[4:] == "00":
        return "SUBSUBSISTEMA"
    if sns[5] == "0":
        return "CONJUNTO"
    return "SUBCONJUNTO"


def derived_parent(sns: str) -> str | None:
    depth = LEVELS.index(derived_level(sns))
    if depth == 0:
        return None
    keep = (2, 3, 4, 5)[depth - 1]
    return sns[:keep] + "0" * (6 - keep)


def pending_mark(description: str) -> str | None:
    """PTE or TBD when the description is still to be written."""
    text = description.strip().upper()
    if text == "PTE":
        return "PTE"
    if text.startswith("TBD"):
        return "TBD"
    return None


def repair_split(description: str | None, overflow: str | None) -> tuple[str, bool]:
    """The description, joined with the ninth column when the source split
    it (CN-005): 'a' + ' b"' -> 'a, b' without the leftover quotes."""
    description = description or ""
    if not overflow:
        return description, False
    # The reader trims both cells: the split came at ", ", put it back.
    joined = ", ".join(part.strip() for part in (description, overflow) if part.strip())
    if joined.startswith('"'):
        joined = joined[1:]
    if joined.endswith('"'):
        joined = joined[:-1]
    return joined.replace('""', '"').strip(), True


@dataclass(frozen=True)
class Row:
    """A row of the file, normalized."""

    row: int
    category_code: str | None
    category_name: str | None
    sub_code: str | None
    subcategory_name: str | None
    declared_level: str
    sns: str
    name: str
    description: str
    repaired: bool = False

    @property
    def subcategory(self) -> str | None:
        return f"{self.category_code}{self.sub_code}" if self.category_code and self.sub_code else None

    def as_json(self) -> dict[str, Any]:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


@dataclass
class Position:
    sns: str
    name: str
    description: str
    description_pending: bool
    level: str
    parent_sns: str | None
    declared_levels: list[str]
    subcategories: list[str]
    extra_names: dict[str, str]  # name -> origin
    first_row: int
    # Each row of the SNS as "subcategory | level | name | description"
    # (with the category names): a change in any single row shows.
    row_signatures: list[str] = field(default_factory=list)
    # The same rows as cells (row_cells()), for the diff's table of rows.
    rows_cells: list[dict[str, Any]] = field(default_factory=list)

    def comparable(self) -> dict[str, Any]:
        """What a diff between versions compares (as text), and the rows."""
        return {
            "name": self.name,
            "description": self.description,
            "levels": ", ".join(self.declared_levels),
            "subcategories": ", ".join(self.subcategories),
            "extra_names": ", ".join(sorted(self.extra_names)),
            "rows": row_signatures_text(self.row_signatures),
            ROW_CELLS: self.rows_cells,
        }


@dataclass
class Catalog:
    rows: list[Row]
    positions: dict[str, Position]
    categories: dict[str, str]
    subcategories: dict[str, tuple[str, str, str]]  # code -> (category, sub_code, name)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)


def row_signature(subcategory: str | None, category_name: str | None, subcategory_name: str | None, level: str, name: str, description: str) -> str:
    where = f"{subcategory} {category_name} / {subcategory_name}" if subcategory else "—"
    return f"{where} | {level} | {name} | {description}"


def row_signatures_text(signatures: list[str]) -> str:
    return "\n".join(sorted(signatures))


# The key of the rows' cells in a comparable position (not compared itself).
ROW_CELLS = "row_cells"
# A field of the SNS and the column of its rows it comes from.
ROW_FIELD = {"name": "name", "description": "description", "levels": "level"}
_ROW_COLUMNS = ("where", "level", "name", "description")


def row_cells(subcategory: str | None, category_name: str | None, subcategory_name: str | None, level: str, name: str, description: str) -> dict[str, Any]:
    where = f"{subcategory} {category_name} / {subcategory_name}" if subcategory else "—"
    return {"subcategory": subcategory, "where": where, "level": level, "name": name, "description": description}


def _row_order(c: dict[str, Any]) -> tuple:
    return (c["subcategory"] or "", c["level"] == ELEMENTO, c["level"], c["name"], c["description"])


def per_subcategory(cells: list[dict[str, Any]], column: str) -> list[dict[str, str]]:
    """The value of one column in each subcategory of an SNS (its main row,
    not the ELEMENTO one), sorted by subcategory."""
    out: dict[str, str] = {}
    for c in sorted(cells, key=_row_order):
        if c["subcategory"] and c["subcategory"] not in out:
            out[c["subcategory"]] = c[column]
    return [{"subcategory": s, "value": v} for s, v in out.items()]


def varies(cells: list[dict[str, Any]], column: str) -> list[dict[str, str]] | None:
    """Every subcategory's value when they are not all the same (the SNS
    has no single value: it is never picked silently, HR7); else None."""
    values = per_subcategory(cells, column)
    return values if len({v["value"] for v in values}) > 1 else None


def align_rows(before: list[dict[str, Any]], after: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The rows of an SNS before and after, side by side by subcategory (the
    n-th row of a subcategory with the n-th), with the columns that changed."""

    def keyed(cells: list[dict[str, Any]]) -> dict[tuple[str, int], dict[str, Any]]:
        out: dict[tuple[str, int], dict[str, Any]] = {}
        seen: dict[str, int] = {}
        for c in sorted(cells, key=_row_order):
            sub = c["subcategory"] or ""
            seen[sub] = seen.get(sub, 0) + 1
            out[(sub, seen[sub])] = c
        return out

    old, new = keyed(before), keyed(after)
    rows = []
    for key in sorted(set(old) | set(new)):
        b, a = old.get(key), new.get(key)
        changed = [col for col in _ROW_COLUMNS if (b or {}).get(col) != (a or {}).get(col)] if b and a else list(_ROW_COLUMNS)
        rows.append({
            "subcategory": key[0] or None,
            "before": {col: b[col] for col in _ROW_COLUMNS} if b else None,
            "after": {col: a[col] for col in _ROW_COLUMNS} if a else None,
            "changed": changed,
        })
    return rows


def _issue(code: str, row: int | None, **params: Any) -> dict[str, Any]:
    return {"code": code, "params": params, "row": row, "column": None, "header": None}


def build_catalog(rows: list[Row]) -> Catalog:
    categories: dict[str, str] = {}
    subcategories: dict[str, tuple[str, str, str]] = {}
    warnings: list[dict[str, Any]] = []
    by_sns: dict[str, list[Row]] = {}
    for r in rows:
        by_sns.setdefault(r.sns, []).append(r)
        if r.subcategory:
            categories.setdefault(r.category_code, r.category_name or "")
            subcategories.setdefault(r.subcategory, (r.category_code, r.sub_code, r.subcategory_name or ""))

    positions: dict[str, Position] = {}
    for sns, group in by_sns.items():
        main = next((r for r in group if r.declared_level != ELEMENTO), group[0])
        written = [r.description for r in group if not pending_mark(r.description)]
        extra: dict[str, str] = {}
        for r in group:
            if r.name != main.name:
                origin = ELEMENTO if r.declared_level == ELEMENTO else OTHER_SUBCATEGORY
                extra[r.name] = ELEMENTO if extra.get(r.name) == ELEMENTO else origin
        positions[sns] = Position(
            sns=sns,
            name=main.name,
            description=written[0] if written else main.description,
            description_pending=not written,
            level=derived_level(sns),
            parent_sns=derived_parent(sns),
            declared_levels=sorted({r.declared_level for r in group}),
            subcategories=sorted({r.subcategory for r in group if r.subcategory}),
            extra_names=extra,
            first_row=group[0].row,
            row_signatures=[
                row_signature(r.subcategory, r.category_name, r.subcategory_name, r.declared_level, r.name, r.description) for r in group
            ],
            rows_cells=[row_cells(r.subcategory, r.category_name, r.subcategory_name, r.declared_level, r.name, r.description) for r in group],
        )

    names_in_sub: dict[tuple[str, str], list[Row]] = {}
    for r in rows:
        if r.subcategory:
            names_in_sub.setdefault((r.subcategory, r.sns), []).append(r)
    cn001: dict[str, list[Row]] = {}
    for (_sub, sns), group in names_in_sub.items():
        if len({r.name for r in group}) > 1:
            cn001.setdefault(sns, []).extend(group)
    for sns, group in cn001.items():
        # A name repeated in the same subcategory is CN-001; one only seen in
        # another subcategory keeps OTHER_SUBCATEGORY.
        for name in {r.name for r in group if r.declared_level != ELEMENTO}:
            if positions[sns].extra_names.get(name) == OTHER_SUBCATEGORY:
                positions[sns].extra_names[name] = "CN-001"
    for sns, group in sorted(cn001.items(), key=lambda item: min(r.row for r in item[1])):
        warnings.append(
            _issue("cn_001", min(r.row for r in group), sns=sns, names=" / ".join(dict.fromkeys(r.name for r in group)),
                   rows=", ".join(str(r.row) for r in sorted(group, key=lambda r: r.row)))
        )
    for r in rows:
        if r.subcategory and r.declared_level != ELEMENTO and r.declared_level != derived_level(r.sns):
            warnings.append(_issue("cn_002", r.row, sns=r.sns, declared=r.declared_level, derived=derived_level(r.sns)))
    for sns, p in positions.items():
        has_place = any(r.subcategory for r in by_sns[sns])
        if has_place and p.parent_sns and p.parent_sns not in positions:
            warnings.append(_issue("cn_003", p.first_row, sns=sns, parent=p.parent_sns))
    for r in rows:
        if not r.category_code and not r.sub_code:
            warnings.append(_issue("cn_004", r.row, sns=r.sns))
        if r.repaired:
            warnings.append(_issue("cn_005", r.row, sns=r.sns))
        mark = pending_mark(r.description)
        if mark:
            warnings.append(_issue("cn_006", r.row, sns=r.sns, mark=mark))
    for sns, p in positions.items():
        # NT §6: an SNS names one function, whatever the subcategory.
        different = varies(p.rows_cells, "description")
        if different:
            values = " · ".join(f"{v['subcategory'][:2]}-{v['subcategory'][2:]}: {v['value']}" for v in different)
            warnings.append(_issue("cn_007", p.first_row, sns=sns, values=values))
    warnings.sort(key=lambda w: (WARNING_CODES.index(w["code"]), w["row"] or 0))

    counts = {
        "rows": len(rows),
        "sns": len(positions),
        "categories": len(categories),
        "subcategories": len(subcategories),
        "uncategorized_rows": sum(1 for r in rows if not r.subcategory),
        "elemento_rows": sum(1 for r in rows if r.declared_level == ELEMENTO),
        "pending_sns": sum(1 for p in positions.values() if p.description_pending),
        **{f"rows_{level.lower()}": sum(1 for r in rows if r.declared_level == level) for level in (*LEVELS, ELEMENTO)},
        **{code: sum(1 for w in warnings if w["code"] == code) for code in WARNING_CODES},
    }
    return Catalog(rows=rows, positions=positions, categories=categories, subcategories=subcategories, warnings=warnings, counts=counts)
