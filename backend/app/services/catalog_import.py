"""The "CONF_FUN (Anexo II)" template (E10) on the app/io_excel engine: the
import of a new catalog version and the export of a version or one
subcategory in the same format (round trip).

Sheet CONF_FUN, one header row, eight columns, plus a ninth without header
that is read only to repair a description the source split (CN-005).
Normalization: the category and subcategory codes are two-digit text
("1" -> "01"), the level and the SNS upper case. Errors that block the
import: an SNS that is not six [A-Z0-9], a level that is not in the
NIVEL_FUNCIONAL reference table, a category or subcategory code that is
not two digits, a row with only one of them.

The analysis compares the file with the active version, SNS by SNS (new,
modified field by field, unchanged, and removed: in the active version but
not in the file), and lists the CN-001..CN-006 warnings
(app/services/catalog.py). Applying creates a new version and makes it the
active one; the previous ones are kept for good (HR9). Categories and
subcategories are shared by every version and reconciled: new ones are
added, a changed name is updated, none is ever deleted.
"""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, insert, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import error_detail
from app.io_excel.reader import Issue, ReadResult
from app.io_excel.targets import register
from app.io_excel.template import Column, Template
from app.models import (
    CatalogVersion,
    ImportJob,
    MaterialCategory,
    MaterialSubcategory,
    SnsExtraName,
    SnsPosition,
    SubcategorySns,
    User,
)
from app.services import audit
from app.services.catalog import (
    ROW_CELLS,
    ROW_FIELD,
    SNS_RE,
    TWO_DIGITS_RE,
    Catalog,
    Row,
    align_rows,
    build_catalog,
    repair_split,
    row_cells,
    row_signature,
    row_signatures_text,
    varies,
)
from app.services.reference import codes_by_state

KIND = "conf_fun"
# pg_advisory_xact_lock key of a catalog apply ("CONF" in ASCII).
_APPLY_LOCK = 0x434F4E46
SHEET = "CONF_FUN"
LEVEL_TABLE = "NIVEL_FUNCIONAL"
TEMPLATE = Template(
    code=KIND,
    sheet=SHEET,
    unique_keys=False,
    columns=(
        Column("category_code", ("ID_CAT_MAT",), max_length=2, zero_pad=2, width=12),
        Column("category_name", ("CAT_MAT",), max_length=200, width=30),
        Column("sub_code", ("ID_SUBCAT_MAT",), max_length=2, zero_pad=2, width=14),
        Column("subcategory_name", ("SUBCAT_MAT",), max_length=200, width=40),
        Column("declared_level", ("NIVEL FUNCIONAL",), max_length=20, required=True, upper=True, ref_table=LEVEL_TABLE, width=18),
        Column("sns", ("ID_CON_FUN",), max_length=6, required=True, key=True, upper=True, width=12),
        Column("name", ("NOMBRE",), max_length=500, required=True, width=40),
        Column("description", ("DESCRIPCIÓN",), max_length=4000, width=70),
        Column("overflow", ("",), max_length=4000, extra=True),
    ),
)
_LETTER = {c.field: chr(ord("A") + i) for i, c in enumerate(TEMPLATE.columns)}
_HEADER = {c.field: c.title for c in TEMPLATE.columns}
_COMPARED = (
    ("name", "NOMBRE"),
    ("description", "DESCRIPCIÓN"),
    ("levels", "NIVEL FUNCIONAL"),
    ("subcategories", "SUBCATEGORÍAS"),
    ("extra_names", "NOMBRES ADICIONALES"),
    # Every row of the SNS: a change in only one subcategory's row (its
    # level, name or description, or the category names) is a change too.
    ("rows", "FILAS"),
)


def _error(code: str, row: int, field: str, **params: Any) -> dict[str, Any]:
    return Issue(code, params, row=row, column=_LETTER[field], header=_HEADER[field]).as_json()


def rows_from_file(read: ReadResult, levels: dict[str, bool]) -> tuple[list[Row], list[dict[str, Any]], list[dict[str, Any]]]:
    """The file's rows as catalog rows, the blocking errors and the
    reader's warnings."""
    errors = [i.as_json() for i in read.errors]
    warnings = [i.as_json() for i in read.warnings]
    rows: list[Row] = []
    for parsed in read.rows:
        errors += [i.as_json() for i in parsed.errors]
        warnings += [i.as_json() for i in parsed.warnings]
        v = parsed.values
        own: list[dict[str, Any]] = []
        for code_field in ("category_code", "sub_code"):
            if v.get(code_field) is not None and not TWO_DIGITS_RE.match(v[code_field]):
                own.append(_error("not_two_digits", parsed.row, code_field))
        if (v.get("category_code") is None) != (v.get("sub_code") is None):
            own.append(_error("subcategory_incomplete", parsed.row, "sub_code"))
        if v.get("sns") is not None and not SNS_RE.match(v["sns"]):
            own.append(_error("sns_invalid", parsed.row, "sns", value=v["sns"]))
        level = v.get("declared_level")
        if level is not None and level not in levels:
            own.append(_error("not_in_table", parsed.row, "declared_level", table=LEVEL_TABLE, value=level))
        elif level is not None and not levels[level]:
            # A new version has no "current" value to keep.
            own.append(_error("inactive_in_table", parsed.row, "declared_level", table=LEVEL_TABLE, value=level))
        errors += own
        if parsed.errors or own:
            continue
        description, repaired = repair_split(v.get("description"), v.get("overflow"))
        rows.append(
            Row(
                row=parsed.row,
                category_code=v.get("category_code"),
                category_name=v.get("category_name"),
                sub_code=v.get("sub_code"),
                subcategory_name=v.get("subcategory_name"),
                declared_level=level,
                sns=v["sns"],
                name=v["name"],
                description=description,
                repaired=repaired,
            )
        )
    return rows, errors, warnings


async def active_version(db: AsyncSession) -> CatalogVersion | None:
    return (await db.execute(select(CatalogVersion).where(CatalogVersion.is_active))).scalar_one_or_none()


async def comparable_positions(db: AsyncSession, version_id: uuid.UUID) -> dict[str, dict[str, Any]]:
    """sns -> the fields a diff compares, for a stored version (only the
    columns it needs: a version has thousands of rows)."""
    positions = (
        await db.execute(
            select(SnsPosition.sns, SnsPosition.name, SnsPosition.description, SnsPosition.declared_levels).where(SnsPosition.version_id == version_id)
        )
    ).all()
    subs: dict[str, set[str]] = {}
    signatures: dict[str, list[str]] = {}
    cells: dict[str, list[dict[str, Any]]] = {}
    for r in await db.execute(
        select(
            SubcategorySns.sns, SubcategorySns.subcategory_code, SubcategorySns.category_name, SubcategorySns.subcategory_name,
            SubcategorySns.declared_level, SubcategorySns.name, SubcategorySns.description,
        ).where(SubcategorySns.version_id == version_id)
    ):
        if r.subcategory_code:
            subs.setdefault(r.sns, set()).add(r.subcategory_code)
        signatures.setdefault(r.sns, []).append(
            row_signature(r.subcategory_code, r.category_name, r.subcategory_name, r.declared_level, r.name, r.description)
        )
        cells.setdefault(r.sns, []).append(row_cells(r.subcategory_code, r.category_name, r.subcategory_name, r.declared_level, r.name, r.description))
    extras: dict[str, list[str]] = {}
    for sns, name in await db.execute(select(SnsExtraName.sns, SnsExtraName.name).where(SnsExtraName.version_id == version_id)):
        extras.setdefault(sns, []).append(name)
    return {
        p.sns: {
            "name": p.name,
            "description": p.description,
            "levels": ", ".join(p.declared_levels),
            "subcategories": ", ".join(sorted(subs.get(p.sns, ()))),
            "extra_names": ", ".join(sorted(extras.get(p.sns, ()))),
            "rows": row_signatures_text(signatures.get(p.sns, [])),
            ROW_CELLS: cells.get(p.sns, []),
        }
        for p in positions
    }


def _change(field: str, header: str, before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    change: dict[str, Any] = {"field": field, "header": header, "before": before[field], "after": after[field]}
    if field in ROW_FIELD:
        # A value that differs per subcategory is shown as such, never one of them.
        for side, position in (("before", before), ("after", after)):
            values = varies(position[ROW_CELLS], ROW_FIELD[field])
            if values:
                change[f"varies_{side}"] = values
    return change


def compare(old: dict[str, dict[str, Any]], new: dict[str, dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """SNS by SNS: new, modified (with the changed fields and, when its rows
    changed, the rows side by side by subcategory), unchanged, removed.
    Each sorted by SNS."""

    def text(position: dict[str, Any]) -> dict[str, str]:
        return {k: v for k, v in position.items() if k != ROW_CELLS}

    out: dict[str, list[dict[str, Any]]] = {"new": [], "modified": [], "unchanged": [], "removed": []}
    for sns in sorted(set(old) | set(new)):
        if sns not in old:
            out["new"].append({"sns": sns, "after": text(new[sns])})
        elif sns not in new:
            out["removed"].append({"sns": sns, "before": text(old[sns])})
        else:
            changes = [_change(f, h, old[sns], new[sns]) for f, h in _COMPARED if old[sns][f] != new[sns][f]]
            item: dict[str, Any] = {"sns": sns, "changes": changes}
            if any(c["field"] == "rows" for c in changes):
                item["rows"] = align_rows(old[sns][ROW_CELLS], new[sns][ROW_CELLS])
            out["modified" if changes else "unchanged"].append(item)
    return out


class ConfFunTarget:
    kind = KIND

    def can_import(self, user: User, params: dict[str, Any]) -> bool:
        return user.is_admin

    async def template(self, db: AsyncSession, params: dict[str, Any]) -> Template:
        return TEMPLATE

    async def stored(self, db: AsyncSession, params: dict[str, Any], template: Template) -> dict:
        return {}

    async def analyze(self, db: AsyncSession, params: dict[str, Any], template: Template, read: ReadResult) -> dict[str, Any]:
        levels = await codes_by_state(db, LEVEL_TABLE)
        rows, errors, warnings = rows_from_file(read, levels)
        # CPU work of thousands of rows: off the event loop, like the reading.
        catalog = await asyncio.to_thread(build_catalog, rows)
        base = await active_version(db)
        old = await comparable_positions(db, base.id) if base else {}
        new = {sns: p.comparable() for sns, p in catalog.positions.items()}
        diff = await asyncio.to_thread(compare, old, new)
        first_row = {sns: p.first_row for sns, p in catalog.positions.items()}
        report = {
            "columns": [{"field": "sns", "header": "ID_CON_FUN"}, {"field": "name", "header": "NOMBRE"}, {"field": "levels", "header": "NIVEL FUNCIONAL"}, {"field": "subcategories", "header": "SUBCATEGORÍAS"}],
            "template_fields": [c.field for c in template.columns],
            "new": [{"row": first_row[d["sns"]], "key": d["sns"], "values": d["after"]} for d in diff["new"]],
            "modified": [
                {"row": first_row[d["sns"]], "key": d["sns"], "changes": d["changes"], **({"rows": d["rows"]} if "rows" in d else {})}
                for d in diff["modified"]
            ],
            "unchanged": [{"row": first_row[d["sns"]], "key": d["sns"]} for d in diff["unchanged"]],
            "removed": [{"row": None, "key": d["sns"], "values": d["before"]} for d in diff["removed"]],
            "errors": errors,
            "warnings": warnings + catalog.warnings,
            "pending": {"base_version_id": str(base.id) if base else None, "rows": [r.as_json() for r in rows]},
        }
        report["counts"] = {
            **catalog.counts,
            "rows": len(read.rows),
            "new": len(report["new"]),
            "modified": len(report["modified"]),
            "unchanged": len(report["unchanged"]),
            "removed": len(report["removed"]),
            "errors": len(errors),
            "rows_with_errors": len({e["row"] for e in errors}),
            "warnings": len(report["warnings"]),
        }
        return report

    async def apply(self, db: AsyncSession, job: ImportJob, template: Template, user: User, ip: str | None) -> None:
        pending = job.report["pending"]
        # One catalog import applied at a time, also when there is no active
        # version yet to lock (the first one).
        await db.execute(text("SELECT pg_advisory_xact_lock(:key)").bindparams(key=_APPLY_LOCK))
        base = (await db.execute(select(CatalogVersion).where(CatalogVersion.is_active).with_for_update())).scalar_one_or_none()
        if (str(base.id) if base else None) != pending["base_version_id"]:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_detail("catalog_version_changed"))
        catalog = build_catalog([Row(**r) for r in pending["rows"]])
        await reconcile_categories(db, catalog)
        number = ((await db.execute(select(func.max(CatalogVersion.number)))).scalar() or 0) + 1
        if base is not None:
            base.is_active = False
            base.version += 1  # a change of the row: an older delete/activate sees it
            await db.flush()
        version = CatalogVersion(
            id=uuid.uuid4(),
            number=number,
            label=job.file_name.rsplit(".", 1)[0],
            file_name=job.file_name,
            file_sha256=job.file_sha256,
            imported_at=datetime.now(timezone.utc),
            user_id=user.id,
            is_active=True,
            counts=catalog.counts,
            warnings=job.report["warnings"],
            notes="",
            version=1,
        )
        db.add(version)
        await db.flush()
        await write_catalog(db, version.id, catalog)
        audit.record(
            db,
            action="catalog_version.imported",
            entity_type="catalog_version",
            entity_id=str(version.id),
            user_id=user.id,
            before={"active_version": base.number} if base else None,
            after={"number": number, "file_name": job.file_name, "counts": catalog.counts},
            ip=ip,
        )

    async def after_apply(self, db: AsyncSession) -> None:
        """Fresh statistics after a bulk load of thousands of rows: without
        them the planner takes the new version for empty."""
        await db.execute(text("ANALYZE sns_position, subcategory_sns, sns_extra_name"))


async def reconcile_categories(db: AsyncSession, catalog: Catalog) -> None:
    stored = {c.code: c for c in (await db.execute(select(MaterialCategory))).scalars()}
    for code, name in catalog.categories.items():
        if code not in stored:
            db.add(MaterialCategory(code=code, name=name))
        elif stored[code].name != name:
            stored[code].name = name
    await db.flush()
    stored_subs = {s.code: s for s in (await db.execute(select(MaterialSubcategory))).scalars()}
    for code, (category, sub_code, name) in catalog.subcategories.items():
        if code not in stored_subs:
            db.add(MaterialSubcategory(code=code, category_code=category, sub_code=sub_code, name=name))
        elif stored_subs[code].name != name:
            stored_subs[code].name = name
    await db.flush()


async def write_catalog(db: AsyncSession, version_id: uuid.UUID, catalog: Catalog) -> None:
    """Bulk inserts: the real file has about 9 600 rows."""
    await db.execute(
        insert(SnsPosition),
        [
            {
                "version_id": version_id, "sns": p.sns, "name": p.name, "description": p.description,
                "description_pending": p.description_pending, "level": p.level, "parent_sns": p.parent_sns,
                "declared_levels": p.declared_levels,
            }
            for p in catalog.positions.values()
        ],
    )
    await db.execute(
        insert(SubcategorySns),
        [
            {
                "version_id": version_id, "row_number": r.row, "subcategory_code": r.subcategory, "category_code": r.category_code,
                "category_name": r.category_name, "sub_code": r.sub_code, "subcategory_name": r.subcategory_name, "sns": r.sns,
                "declared_level": r.declared_level, "name": r.name, "description": r.description, "description_repaired": r.repaired,
            }
            for r in catalog.rows
        ],
    )
    extras = [
        {"version_id": version_id, "sns": p.sns, "name": name, "origin": origin}
        for p in catalog.positions.values()
        for name, origin in p.extra_names.items()
    ]
    if extras:
        await db.execute(insert(SnsExtraName), extras)


async def export_rows(db: AsyncSession, version_id: uuid.UUID, subcategory: str | None) -> list[dict[str, Any]]:
    """The version's rows (or one subcategory's) as template fields, in the
    file's order."""
    query = select(SubcategorySns).where(SubcategorySns.version_id == version_id)
    if subcategory:
        query = query.where(SubcategorySns.subcategory_code == subcategory)
    rows = (await db.execute(query.order_by(SubcategorySns.row_number))).scalars()
    return [
        {
            "category_code": r.category_code, "category_name": r.category_name, "sub_code": r.sub_code,
            "subcategory_name": r.subcategory_name, "declared_level": r.declared_level, "sns": r.sns, "name": r.name,
            "description": r.description or None,
        }
        for r in rows
    ]


register(ConfFunTarget())
