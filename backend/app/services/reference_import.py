"""The "Tabla de referencia" template (E03): the first consumer of
app/io_excel. One sheet named after the table, one header row, the
columns Código (the key), Descripción, Definición, Activo (S/N) and one
column per attribute of the table's schema, by its readable name.

Importing adds the new values (active or not, as the file says, after the
last one) and updates the description, definition, state and attributes of
the existing ones; a value of the table that is not in the file is left as
it is (nothing is ever deleted, HR9). Only an admin imports.

D114's numeric codes all have two digits, so a 2 typed in Excel is read as
"02" (zero_pad, with a warning); a table whose numeric codes have mixed or
single-digit widths gets no padding.
"""

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import error_detail
from app.io_excel.analysis import Stored
from app.io_excel.cells import from_json
from app.io_excel.targets import register
from app.io_excel.template import Column, ColumnType, Template
from app.models import (
    REFERENCE_CODE_MAX_LENGTH,
    REFERENCE_DEFINITION_MAX_LENGTH,
    REFERENCE_DESCRIPTION_MAX_LENGTH,
    ImportJob,
    ReferenceTable,
    ReferenceValue,
    User,
)
from app.services import audit

KIND = "reference_table"
_ATTRIBUTE_TYPES = {"texto": ColumnType.TEXT, "entero": ColumnType.INTEGER, "si_no": ColumnType.YES_NO}
_ATTR = "attr:"


def reference_table_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_detail("reference_table_not_found"))


def value_snapshot(v: ReferenceValue) -> dict[str, Any]:
    return {
        "table": v.table_code,
        "code": v.code,
        "description": v.description,
        "definition": v.definition,
        "attributes": v.attributes,
        "is_active": v.is_active,
        "sort_order": v.sort_order,
    }


def zero_pad(codes: list[str]) -> int | None:
    """The width numeric codes are padded to: their common width, when all
    of them have the same one and it is over 1."""
    widths = {len(c) for c in codes if c.isdigit()}
    return widths.pop() if len(widths) == 1 and min(widths) > 1 else None


def build_template(table: ReferenceTable, codes: list[str]) -> Template:
    columns = [
        Column("code", ("Código",), max_length=REFERENCE_CODE_MAX_LENGTH, required=True, key=True, zero_pad=zero_pad(codes), width=14),
        Column("description", ("Descripción",), max_length=REFERENCE_DESCRIPTION_MAX_LENGTH, required=True, width=50),
        Column("definition", ("Definición",), max_length=REFERENCE_DEFINITION_MAX_LENGTH, width=60),
        Column("is_active", ("Activo",), ColumnType.YES_NO, required=True, width=8),
    ]
    for spec in table.attribute_schema:
        columns.append(
            Column(
                _ATTR + spec["key"],
                (spec["name"],),
                _ATTRIBUTE_TYPES[spec["type"]],
                max_length=REFERENCE_DESCRIPTION_MAX_LENGTH if spec["type"] == "texto" else None,
                required=spec.get("required", False),
                choices=tuple((o["code"], o["name"]) for o in spec.get("options") or []),
                width=max(14, len(spec["name"]) + 2),
            )
        )
    return Template(code=KIND, sheet=table.code, columns=tuple(columns))


def template_values(v: ReferenceValue) -> dict[str, Any]:
    """A stored value as the template's fields."""
    values = {"code": v.code, "description": v.description, "definition": v.definition, "is_active": v.is_active}
    values.update({_ATTR + k: a for k, a in v.attributes.items()})
    return values


def _from_template(template: Template, values: dict[str, Any]) -> dict[str, Any]:
    by_field = {c.field: c for c in template.columns}
    decoded = {f: from_json(by_field[f], v) for f, v in values.items()}
    return {
        "description": decoded["description"],
        "definition": decoded.get("definition"),
        "is_active": decoded["is_active"],
        "attributes": {f[len(_ATTR) :]: v for f, v in decoded.items() if f.startswith(_ATTR) and v is not None},
    }


async def get_table(db: AsyncSession, code: str, *, for_update: bool = False) -> ReferenceTable:
    query = select(ReferenceTable).where(ReferenceTable.code == code)
    table = (await db.execute(query.with_for_update() if for_update else query)).scalar_one_or_none()
    if table is None:
        raise reference_table_not_found()
    return table


async def table_values(db: AsyncSession, code: str) -> list[ReferenceValue]:
    return list(
        (await db.execute(select(ReferenceValue).where(ReferenceValue.table_code == code).order_by(ReferenceValue.sort_order, ReferenceValue.code))).scalars()
    )


async def template_for(db: AsyncSession, code: str) -> Template:
    table = await get_table(db, code)
    return build_template(table, [v.code for v in await table_values(db, code)])


class ReferenceTableTarget:
    kind = KIND

    def can_import(self, user: User, params: dict[str, Any]) -> bool:
        return user.is_admin

    async def template(self, db: AsyncSession, params: dict[str, Any]) -> Template:
        return await template_for(db, params["table"])

    async def stored(self, db: AsyncSession, params: dict[str, Any], template: Template) -> dict[tuple[Any, ...], Stored]:
        return {(v.code,): Stored(template_values(v), str(v.id), v.version) for v in await table_values(db, params["table"])}

    async def apply(self, db: AsyncSession, job: ImportJob, template: Template, user: User, ip: str | None) -> None:
        table = await get_table(db, job.params["table"], for_update=True)
        if not table.editable:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_detail("reference_table_not_editable"))
        pending = job.report["pending"]
        for item in pending["modified"]:
            value = (await db.execute(select(ReferenceValue).where(ReferenceValue.id == item["ref"]).with_for_update())).scalar_one_or_none()
            if value is None or value.version != item["version"]:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_detail("import_stale", row=item["row"]))
            before = value_snapshot(value)
            for name, new in _from_template(template, item["values"]).items():
                setattr(value, name, new)
            value.version += 1
            audit.record(
                db, action="reference_value.updated", entity_type="reference_value", entity_id=str(value.id),
                user_id=user.id, before=before, after=value_snapshot(value), ip=ip,
            )
        next_order = (await db.execute(select(func.max(ReferenceValue.sort_order)).where(ReferenceValue.table_code == table.code))).scalar() or 0
        for item in pending["new"]:
            code = from_json(template.columns[0], item["values"]["code"])
            if (await db.execute(select(ReferenceValue.id).where(ReferenceValue.table_code == table.code, ReferenceValue.code == code))).first():
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_detail("import_stale", row=item["row"]))
            next_order += 1
            value = ReferenceValue(table_code=table.code, code=code, sort_order=next_order, version=1, **_from_template(template, item["values"]))
            db.add(value)
            await db.flush()
            audit.record(
                db, action="reference_value.created", entity_type="reference_value", entity_id=str(value.id),
                user_id=user.id, after=value_snapshot(value), ip=ip,
            )
        if pending["new"] or pending["modified"]:
            table.version += 1


register(ReferenceTableTarget())
