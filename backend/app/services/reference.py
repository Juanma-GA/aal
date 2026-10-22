"""Reference tables at run time (E03): resolve a code, check a value's
attributes against its table's schema, and the reusable validator the
modules' schemas use (E10-E19).

    class ArticleIn(StrictModel):
        security_code: Annotated[str | None, must_be_in("D106")] = None

    await validate_references(db, body, current=stored_values)

`must_be_in(table)` only marks the field (a Pydantic validator cannot query
the database); `validate_references()` checks every marked field of a
model: the code must exist in the table and, for new data, be active. A
value equal to the one already stored (`current`) passes even when it was
deactivated since: a deactivated value still resolves for the data that
already uses it (HR9).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import error_detail
from app.models import ReferenceValue


async def resolve(db: AsyncSession, table: str, code: str) -> ReferenceValue | None:
    """The value `code` of `table`, active or not, or None."""
    return (
        await db.execute(select(ReferenceValue).where(ReferenceValue.table_code == table, ReferenceValue.code == code))
    ).scalar_one_or_none()


async def codes_by_state(db: AsyncSession, table: str) -> dict[str, bool]:
    """Every code of `table` -> whether it is active."""
    rows = await db.execute(select(ReferenceValue.code, ReferenceValue.is_active).where(ReferenceValue.table_code == table))
    return {code: active for code, active in rows}


@dataclass(frozen=True)
class ReferenceIn:
    """Marks a schema field whose value must be a code of `table`."""

    table: str


def must_be_in(table: str) -> ReferenceIn:
    return ReferenceIn(table)


def reference_fields(model: type[BaseModel]) -> dict[str, str]:
    """Field name -> reference table, for the fields marked with must_be_in."""
    found = {}
    for name, info in model.model_fields.items():
        for meta in info.metadata:
            if isinstance(meta, ReferenceIn):
                found[name] = meta.table
    return found


async def validate_references(db: AsyncSession, model: BaseModel, current: Mapping[str, Any] | None = None) -> None:
    """422 reference_value_unknown / reference_value_inactive for the first
    marked field whose code does not pass (see the module docstring)."""
    for name, table in reference_fields(type(model)).items():
        value = getattr(model, name)
        if value is None:
            continue
        row = await resolve(db, table, value)
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=error_detail("reference_value_unknown", field=name, table=table),
            )
        if not row.is_active and (current is None or current.get(name) != value):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=error_detail("reference_value_inactive", field=name, table=table),
            )


def attribute_problem(schema: list[dict[str, Any]], attributes: Mapping[str, Any]) -> tuple[str, dict[str, Any]] | None:
    """Why `attributes` do not fit the table's attribute schema, as (error
    code, params), or None. A key the schema does not declare, a value of
    the wrong type (texto: non-empty text without surrounding spaces;
    entero: an integer; si_no: true/false), an option that is not listed
    and a required attribute that is missing are all refused; an absent
    optional attribute is simply not stored (never None)."""
    declared = {a["key"]: a for a in schema}
    for key, value in attributes.items():
        spec = declared.get(key)
        if spec is None:
            return "attribute_unknown", {"attribute": key}
        kind = spec["type"]
        valid = (
            (kind == "texto" and isinstance(value, str) and value != "" and value == value.strip())
            or (kind == "entero" and isinstance(value, int) and not isinstance(value, bool))
            or (kind == "si_no" and isinstance(value, bool))
        )
        if not valid:
            return "attribute_invalid", {"attribute": spec["name"]}
        options = spec.get("options") or []
        if options and value not in {o["code"] for o in options}:
            return "attribute_option_invalid", {"attribute": spec["name"]}
    for spec in schema:
        if spec.get("required") and spec["key"] not in attributes:
            return "attribute_required", {"attribute": spec["name"]}
    return None
