"""The reference tables seed (E03): read, check and load
app/seeds/reference_tables_seed.yaml.

- `read_seed()` parses the YAML exactly as written: a code is never turned
  into text here, so a code YAML read as a number (an unquoted 0 or 09) is
  caught by `check_seed()`, never stored as "9".
- `check_seed()` lists every problem: duplicate table, value or field
  codes, a code that is not text (or empty, or with surrounding spaces, or
  too long), attributes that do not fit their table's schema, a field whose
  `tabla_referencia` is not a table of the seed.
- `load_reference_tables(conn)` writes it, idempotently, on a synchronous
  connection (the migration's own, or `AsyncConnection.run_sync`):
  - new tables and new values are added;
  - a value already in the database is never modified (an admin may have
    edited it): where it differs from the seed, the report says so;
  - a table's name, source, note and attribute schema, and the article
    fields, are not editable in the app and follow the seed.
- `load_article_field_extras(conn)` (E12, migration 0008 and the reload
  script) writes what the article fields gained after migration 0004: the
  column's name in the official Fichero Carga (`cabecera`), the values of a
  S/N field (`valores`) and the MAR06 help of app/seeds/article_field_help.yaml,
  matched by `campo_guia` (several fields may share one: 58 is the four
  maintenance levels; a field without one, cdPolEl, has none).
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import Connection, func, insert, select, update

from app.models import ATTRIBUTE_TYPES, REFERENCE_CODE_MAX_LENGTH, ArticleFieldDefinition, ReferenceTable, ReferenceValue
from app.services.reference import attribute_problem

SEED_PATH = Path(__file__).resolve().parents[1] / "seeds" / "reference_tables_seed.yaml"
HELP_PATH = Path(__file__).resolve().parents[1] / "seeds" / "article_field_help.yaml"
# The help's keys kept for a field (the document's own words).
_HELP_KEYS = ("titulo", "importancia", "tipo", "tamano", "definicion", "finalidad", "observaciones")


class SeedError(ValueError):
    """The seed does not pass its checks (`problems` lists them all)."""

    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


@dataclass(frozen=True)
class SeedValue:
    code: Any  # text once check_seed() passes
    description: str
    definition: str | None
    attributes: dict[str, Any]


@dataclass(frozen=True)
class SeedTable:
    code: str
    name: str
    source: str
    note: str | None
    attribute_schema: list[dict[str, Any]]
    values: list[SeedValue]


@dataclass(frozen=True)
class Seed:
    tables: list[SeedTable]
    fields: list[dict[str, Any]]


def _schema(raw: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    return [
        {
            "key": a["clave"],
            "name": a["nombre"],
            "type": a["tipo"],
            "required": bool(a.get("obligatorio", False)),
            "options": [{"code": o["codigo"], "name": o["nombre"]} for o in a.get("opciones") or []],
        }
        for a in raw or []
    ]


def read_seed(path: Path = SEED_PATH) -> Seed:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    tables = [
        SeedTable(
            code=t["codigo"],
            name=t["nombre"],
            source=t.get("fuente") or "",
            note=t.get("nota"),
            attribute_schema=_schema(t.get("atributos_definicion")),
            values=[
                SeedValue(
                    code=v["codigo"],
                    description=v["descripcion"],
                    definition=v.get("definicion"),
                    attributes=dict(v.get("atributos") or {}),
                )
                for v in t["valores"]
            ],
        )
        for t in data["tablas"]
    ]
    fields = [
        {
            "prisma_code": f["codigo_prisma"],
            "name": f["nombre"],
            "importance": f["importancia"],
            "guide_field": f["campo_guia"],
            "data_type": f["tipo"],
            "length": f.get("longitud"),
            "decimals": f.get("decimales"),
            "related_to": f.get("relacionado_con"),
            "supplied_by_contractor": f["suministrado_por_contratista"],
            "reference_table_code": f.get("tabla_referencia"),
            "sort_order": position,
        }
        for position, f in enumerate(data["campos_articulo"], start=1)
    ]
    return Seed(tables=tables, fields=fields)


def code_problem(code: Any) -> str | None:
    """Why `code` cannot be a reference value's code, or None."""
    if not isinstance(code, str):
        return f"the code {code!r} is not text (quote it in the YAML)"
    if code == "" or code != code.strip():
        return f"the code {code!r} is empty or has surrounding spaces"
    if len(code) > REFERENCE_CODE_MAX_LENGTH:
        return f"the code {code!r} is longer than {REFERENCE_CODE_MAX_LENGTH}"
    return None


def check_seed(seed: Seed) -> list[str]:
    problems: list[str] = []
    table_codes = [t.code for t in seed.tables]
    for code in sorted({c for c in table_codes if table_codes.count(c) > 1}):
        problems.append(f"duplicate table {code}")
    for t in seed.tables:
        for spec in t.attribute_schema:
            if spec["type"] not in ATTRIBUTE_TYPES:
                problems.append(f"{t.code}: attribute {spec['key']} has an unknown type {spec['type']}")
        codes = [v.code for v in t.values]
        for code in sorted({repr(c) for c in codes if codes.count(c) > 1}):
            problems.append(f"{t.code}: duplicate value {code}")
        for v in t.values:
            problem = code_problem(v.code)
            if problem:
                problems.append(f"{t.code}: {problem}")
            if not isinstance(v.description, str) or not v.description.strip():
                problems.append(f"{t.code}/{v.code}: no description")
            wrong = attribute_problem(t.attribute_schema, v.attributes)
            if wrong:
                problems.append(f"{t.code}/{v.code}: {wrong[0]} {wrong[1]}")
    prisma = [f["prisma_code"] for f in seed.fields]
    for code in sorted({c for c in prisma if prisma.count(c) > 1}):
        problems.append(f"duplicate article field {code}")
    for f in seed.fields:
        ref = f["reference_table_code"]
        if ref is not None and ref not in table_codes:
            problems.append(f"article field {f['prisma_code']}: unknown reference table {ref}")
    return problems


@dataclass(frozen=True)
class Difference:
    """A value of the database that differs from the seed (kept as is)."""

    table: str
    code: str
    field: str
    stored: Any
    seed: Any


@dataclass
class LoadReport:
    tables_added: int = 0
    values_added: int = 0
    fields_added: int = 0
    fields_updated: int = 0
    differences: list[Difference] = field(default_factory=list)
    # "TABLE/CODE" in the database that the seed does not have (kept).
    values_not_in_seed: list[str] = field(default_factory=list)


def load_reference_tables(conn: Connection, seed: Seed | None = None) -> LoadReport:
    seed = seed or read_seed()
    problems = check_seed(seed)
    if problems:
        raise SeedError(problems)
    report = LoadReport()

    stored_tables = set(conn.execute(select(ReferenceTable.code)).scalars())
    for position, t in enumerate(seed.tables, start=1):
        meta = {"name": t.name, "source": t.source, "note": t.note, "attribute_schema": t.attribute_schema, "sort_order": position}
        if t.code in stored_tables:
            conn.execute(update(ReferenceTable).where(ReferenceTable.code == t.code).values(**meta))
        else:
            conn.execute(insert(ReferenceTable).values(code=t.code, editable=True, version=1, **meta))
            report.tables_added += 1

        stored = {
            row.code: row
            for row in conn.execute(
                select(ReferenceValue.code, ReferenceValue.description, ReferenceValue.definition, ReferenceValue.attributes).where(
                    ReferenceValue.table_code == t.code
                )
            )
        }
        next_order = (conn.execute(select(func.max(ReferenceValue.sort_order)).where(ReferenceValue.table_code == t.code)).scalar() or 0) + 1
        for v in t.values:
            row = stored.get(v.code)
            if row is None:
                conn.execute(
                    insert(ReferenceValue).values(
                        table_code=t.code,
                        code=v.code,
                        description=v.description,
                        definition=v.definition,
                        attributes=v.attributes,
                        is_active=True,
                        sort_order=next_order,
                        version=1,
                    )
                )
                next_order += 1
                report.values_added += 1
                continue
            for name in ("description", "definition", "attributes"):
                if getattr(row, name) != getattr(v, name):
                    report.differences.append(Difference(t.code, v.code, name, getattr(row, name), getattr(v, name)))
        in_seed = {v.code for v in t.values}
        report.values_not_in_seed += [f"{t.code}/{code}" for code in sorted(set(stored) - in_seed)]

    # Only the columns migration 0004 creates: this loader runs inside that
    # migration, so it must not depend on columns a later one may add.
    columns = [getattr(ArticleFieldDefinition, name) for name in seed.fields[0]] if seed.fields else [ArticleFieldDefinition.prisma_code]
    stored_fields = {row.prisma_code: row for row in conn.execute(select(*columns))}
    for f in seed.fields:
        row = stored_fields.get(f["prisma_code"])
        if row is None:
            conn.execute(insert(ArticleFieldDefinition).values(**f))
            report.fields_added += 1
        elif any(getattr(row, name) != value for name, value in f.items()):
            conn.execute(update(ArticleFieldDefinition).where(ArticleFieldDefinition.prisma_code == f["prisma_code"]).values(**f))
            report.fields_updated += 1
    return report


def read_field_extras(seed_path: Path = SEED_PATH, help_path: Path = HELP_PATH) -> dict[str, dict[str, Any]]:
    """prisma code -> {header, allowed_values, help} (see the docstring)."""
    fields = yaml.safe_load(seed_path.read_text(encoding="utf-8"))["campos_articulo"]
    help_doc = yaml.safe_load(help_path.read_text(encoding="utf-8"))
    by_guide = {str(h["campo_guia"]): {k: h.get(k) for k in _HELP_KEYS} for h in help_doc["campos"]}
    extras = {}
    for f in fields:
        values = f.get("valores")
        extras[f["codigo_prisma"]] = {
            "header": f.get("cabecera"),
            "allowed_values": [str(v) for v in values] if values else None,
            "help": by_guide.get(str(f["campo_guia"])),
        }
    return extras


def check_field_extras(extras: dict[str, dict[str, Any]]) -> list[str]:
    problems = []
    for code, e in extras.items():
        if not e["header"]:
            problems.append(f"article field {code}: no cabecera")
        if e["allowed_values"] is not None and any(len(v) != 1 for v in e["allowed_values"]):
            problems.append(f"article field {code}: valores must be one character each")
    return problems


def load_article_field_extras(conn: Connection, extras: dict[str, dict[str, Any]] | None = None) -> int:
    """Writes the extras over the stored fields; returns how many changed."""
    extras = extras if extras is not None else read_field_extras()
    problems = check_field_extras(extras)
    if problems:
        raise SeedError(problems)
    stored = {
        row.prisma_code: row
        for row in conn.execute(
            select(ArticleFieldDefinition.prisma_code, ArticleFieldDefinition.header, ArticleFieldDefinition.allowed_values, ArticleFieldDefinition.help)
        )
    }
    changed = 0
    for code, e in extras.items():
        row = stored.get(code)
        if row is not None and (row.header, row.allowed_values, row.help) != (e["header"], e["allowed_values"], e["help"]):
            conn.execute(update(ArticleFieldDefinition).where(ArticleFieldDefinition.prisma_code == code).values(**e))
            changed += 1
    return changed
