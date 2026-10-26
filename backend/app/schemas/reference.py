import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints

from app.models import REFERENCE_CODE_MAX_LENGTH, REFERENCE_DEFINITION_MAX_LENGTH, REFERENCE_DESCRIPTION_MAX_LENGTH
from app.schemas.common import StrictModel

Code = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=REFERENCE_CODE_MAX_LENGTH)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=REFERENCE_DESCRIPTION_MAX_LENGTH)]
Definition = Annotated[str, StringConstraints(strip_whitespace=True, max_length=REFERENCE_DEFINITION_MAX_LENGTH)]
# An attribute's value: text, integer or yes/no (the table's schema says
# which; app/services/reference.attribute_problem checks it).
AttributeValue = Annotated[str, StringConstraints(strip_whitespace=True, max_length=REFERENCE_DESCRIPTION_MAX_LENGTH)] | bool | int


class AttributeOption(BaseModel):
    code: str
    name: str


class AttributeSpec(BaseModel):
    key: str
    name: str
    type: str
    required: bool
    options: list[AttributeOption]


class ReferenceTableOut(BaseModel):
    code: str
    name: str
    source: str
    note: str | None
    editable: bool
    attribute_schema: list[AttributeSpec]
    value_count: int
    active_count: int
    version: int


class ReferenceValueOut(BaseModel):
    id: uuid.UUID
    code: str
    description: str
    definition: str | None
    attributes: dict[str, Any]
    is_active: bool
    sort_order: int
    version: int
    updated_at: datetime


class ReferenceValueCreate(StrictModel):
    code: Code
    description: Description
    definition: Definition | None = None
    attributes: dict[str, AttributeValue] = Field(default_factory=dict)


class ReferenceValueUpdate(StrictModel):
    version: int
    description: Description | None = None
    # null (or "") clears it.
    definition: Definition | None = None
    attributes: dict[str, AttributeValue] | None = None
    is_active: bool | None = None


class ReferenceOrderIn(StrictModel):
    # The table's version (reordering changes the whole table).
    version: int
    # Every value of the table, in the new order.
    value_ids: list[uuid.UUID]


class ArticleFieldOut(BaseModel):
    prisma_code: str
    name: str
    importance: str
    guide_field: str
    data_type: str
    length: int | None
    decimals: int | None
    related_to: str | None
    supplied_by_contractor: str
    reference_table_code: str | None
    reference_table_name: str | None
    # E12: its name in the Fichero Carga, its S/N values, its MAR06 help.
    header: str | None = None
    allowed_values: list[str] | None = None
    help: dict[str, Any] | None = None
    # E13: corrected by the admin (a seed reload keeps it), and its version.
    edited_by_admin: bool = False
    version: int = 1


class ArticleFieldUpdate(StrictModel):
    """The admin's correction of a field definition (E13): only what is sent
    changes. Length and decimals as digits (numbers) or characters (text)."""

    version: int
    name: str | None = Field(default=None, min_length=1, max_length=200)
    importance: Literal["Obligatorio", "Recomendado", "Opcional"] | None = None
    length: int | None = Field(default=None, ge=1, le=4000)
    decimals: int | None = Field(default=None, ge=0, le=20)
    related_to: str | None = Field(default=None, max_length=100)
    supplied_by_contractor: str | None = Field(default=None, min_length=1, max_length=200)
    reference_table_code: str | None = Field(default=None, max_length=40)


class ImportIssueOut(BaseModel):
    code: str
    params: dict[str, Any]
    row: int | None
    column: str | None
    header: str | None


class ImportReportOut(BaseModel):
    columns: list[dict[str, str]]
    new: list[dict[str, Any]]
    modified: list[dict[str, Any]]
    unchanged: list[dict[str, Any]]
    # Records the file no longer has (a target whose import replaces the
    # whole set, the CONF_FUN catalog); absent otherwise.
    removed: list[dict[str, Any]] | None = None
    errors: list[ImportIssueOut]
    warnings: list[ImportIssueOut]
    # Articles (E12): rows refused (with their row and reasons; they do not
    # block applying the rest), the AR findings by rule and the AR-008
    # corrections; absent for the other templates.
    rejected: list[dict[str, Any]] | None = None
    ar: dict[str, list[dict[str, Any]]] | None = None
    corrections: list[dict[str, Any]] | None = None
    # The Maestro AAL's "Referencias" sheet (E15): new, unchanged (a count), rejected, notices.
    references: dict[str, Any] | None = None
    # A book of several sheets (E15, the Anexo XI): its report by sheet, the sheets ignored and its notices.
    sheets: dict[str, Any] | None = None
    ignored_sheets: list[str] | None = None
    notices: list[dict[str, Any]] | None = None
    # The Anexo XI (E15): its mode, the CUF of the file against the material's, and what the result would have.
    mode: str | None = None
    cuf: dict[str, Any] | None = None
    result: dict[str, Any] | None = None


class ImportJobOut(BaseModel):
    id: uuid.UUID
    template: str
    params: dict[str, Any]
    status: str
    file_name: str
    counts: dict[str, int]
    # The report once analysed ("pending", what apply writes, stays on the
    # server).
    report: ImportReportOut | None
    error_code: str | None
    error_params: dict[str, Any]
    created_at: datetime
    analyzed_at: datetime | None
    applied_at: datetime | None
