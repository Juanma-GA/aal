"""Articles (E12): what the API reads and writes. Field values go by
PRISMA code (`fields`); they are checked against article_field_definition
in the route (app/services/article_fields.py), not here."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from app.models import MAX_LIFE_CONTROLS
from app.schemas.common import StrictModel

FieldValue = str | int | float | Decimal | None


class LifeControlIn(StrictModel):
    unit_code: str | None = Field(default=None, max_length=10)
    quantity: str | int | float | Decimal | None = None


class ArticleIn(StrictModel):
    noc: str | None = Field(default=None, max_length=40)
    pn: str | None = Field(default=None, max_length=32)
    ncage: str | None = Field(default=None, max_length=20)
    nombre: str = Field(min_length=1, max_length=200)
    origen_nombre: Literal["coloquial", "aprobado", "comercial"] = "coloquial"
    fields: dict[Annotated[str, Field(max_length=40)], FieldValue] = Field(default_factory=dict, max_length=40)
    life_controls: list[LifeControlIn] = Field(default_factory=list, max_length=MAX_LIFE_CONTROLS)


class ArticleUpdate(StrictModel):
    """Only what is sent changes; `fields` merges over the stored ones."""

    version: int
    noc: str | None = Field(default=None, max_length=40)
    pn: str | None = Field(default=None, max_length=32)
    ncage: str | None = Field(default=None, max_length=20)
    nombre: str | None = Field(default=None, min_length=1, max_length=200)
    origen_nombre: Literal["coloquial", "aprobado", "comercial"] | None = None
    fields: dict[Annotated[str, Field(max_length=40)], FieldValue] = Field(default_factory=dict, max_length=40)
    life_controls: list[LifeControlIn] | None = Field(default=None, max_length=MAX_LIFE_CONTROLS)


class BatchItem(StrictModel):
    id: uuid.UUID
    version: int
    fields: dict[Annotated[str, Field(max_length=40)], FieldValue] = Field(max_length=40)


class BatchIn(StrictModel):
    items: list[BatchItem] = Field(min_length=1, max_length=500)


class Finding(BaseModel):
    code: str
    severity: str
    field: str
    problem: str
    params: dict[str, Any]


class LifeControlOut(BaseModel):
    position: int
    unit_code: str | None
    quantity: str | None


class ArticleRow(BaseModel):
    id: uuid.UUID
    noc: str | None
    pn: str | None
    ncage: str | None
    nombre: str
    origen_nombre: str
    fields: dict[str, Any]
    life_controls: list[LifeControlOut]
    finding_codes: list[str]
    version: int


class ArticlePage(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[ArticleRow]


class ArticleOut(ArticleRow):
    findings: list[Finding]
    where_used: list[dict[str, Any]]
    corrections: list[dict[str, Any]] = []
    created_at: datetime
    updated_at: datetime
    created_by: str | None
    updated_by: str | None


class BatchResult(BaseModel):
    id: uuid.UUID
    ok: bool
    article: ArticleRow | None = None
    error: dict[str, Any] | None = None


class ArticleRights(BaseModel):
    can_edit: bool
    can_import: bool


class ExportSummary(BaseModel):
    articles: int
    with_findings: int
    by_rule: dict[str, int]
