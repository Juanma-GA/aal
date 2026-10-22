"""A read file against what is stored: the import report. Nothing is
written anywhere.

Each row without errors is matched by its key with a stored record:
- no record: new;
- a record whose values all equal the row's: unchanged;
- otherwise: modified, with every changed field (before -> after).

Reference columns are checked here, where the stored record is known: the
code must exist in the table and be active, except when it is the value
the record already has (a deactivated value still stands for the data that
uses it). A row with any error is only an error: it is neither new nor
modified, and any error blocks applying the import.

The report holds what the person reviews (shown values) and, under
"pending", what applying will write (JSON values and, for a modified row,
the record and its version, so a record changed after the analysis is
detected instead of overwritten).
"""

from dataclasses import dataclass
from typing import Any

from openpyxl.utils import get_column_letter

from app.io_excel.cells import display, to_json
from app.io_excel.reader import Issue, ParsedRow, ReadResult, row_key
from app.io_excel.template import Template


@dataclass(frozen=True)
class Stored:
    """A stored record as the template sees it."""

    values: dict[str, Any]
    ref: str  # its id
    version: int


def _check_references(template: Template, row: ParsedRow, stored: Stored | None, references: dict[str, dict[str, bool]]) -> None:
    for i, col in enumerate(template.columns):
        value = row.values.get(col.field)
        if col.ref_table is None or value is None:
            continue
        where = {"row": row.row, "column": _letter(i), "header": col.title}
        active = references.get(col.ref_table, {}).get(value)
        if active is None:
            row.errors.append(Issue("not_in_table", {"table": col.ref_table, "value": value}, **where))
        elif not active and (stored is None or stored.values.get(col.field) != value):
            row.errors.append(Issue("inactive_in_table", {"table": col.ref_table, "value": value}, **where))


def _letter(index: int) -> str:
    return get_column_letter(index + 1)


def _key_text(template: Template, values: dict[str, Any]) -> str:
    return " / ".join(display(c, values.get(c.field)) for c in template.key_columns)


def analyze(
    template: Template,
    read: ReadResult,
    stored: dict[tuple[Any, ...], Stored],
    references: dict[str, dict[str, bool]] | None = None,
) -> dict[str, Any]:
    references = references or {}
    report: dict[str, Any] = {
        "columns": [{"field": c.field, "header": c.title} for c in template.columns],
        "new": [],
        "modified": [],
        "unchanged": [],
        "errors": [i.as_json() for i in read.errors],
        "warnings": [i.as_json() for i in read.warnings],
        "pending": {"new": [], "modified": []},
    }
    by_field = {c.field: c for c in template.columns}
    rows_with_errors = 0
    for row in read.rows:
        key = row_key(template, row.values)
        record = stored.get(key) if key is not None else None
        _check_references(template, row, record, references)
        report["warnings"] += [i.as_json() for i in row.warnings]
        if row.errors:
            rows_with_errors += 1
            report["errors"] += [i.as_json() for i in row.errors]
            continue
        shown = {f: display(by_field[f], v) for f, v in row.values.items()}
        as_json = {f: to_json(by_field[f], v) for f, v in row.values.items()}
        if record is None:
            report["new"].append({"row": row.row, "key": _key_text(template, row.values), "values": shown})
            report["pending"]["new"].append({"row": row.row, "values": as_json})
            continue
        changes = [
            {"field": c.field, "header": c.title, "before": display(c, record.values.get(c.field)), "after": shown[c.field]}
            for c in template.columns
            if not c.key and record.values.get(c.field) != row.values.get(c.field)
        ]
        if not changes:
            report["unchanged"].append({"row": row.row, "key": _key_text(template, row.values)})
            continue
        report["modified"].append({"row": row.row, "key": _key_text(template, row.values), "changes": changes})
        report["pending"]["modified"].append({"row": row.row, "ref": record.ref, "version": record.version, "values": as_json})
    report["counts"] = {
        "rows": len(read.rows),
        "new": len(report["new"]),
        "modified": len(report["modified"]),
        "unchanged": len(report["unchanged"]),
        "errors": len(report["errors"]),
        "rows_with_errors": rows_with_errors,
        "warnings": len(report["warnings"]),
    }
    return report
