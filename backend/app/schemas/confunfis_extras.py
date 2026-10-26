"""The rest of RF-02 (E14): the parts table of an article, the functional
products, the extra functions and the incompatibilities of a CUF."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from app.schemas.common import StrictModel

_Short = Field(default=None, max_length=40)
_Number = Annotated[str, Field(max_length=40)] | int | float | Decimal | None


class ArticleBrief(BaseModel):
    """An article as the CONFUNFIS shows it (E13), with the P/N + NCAGE
    its row or part uses."""

    id: uuid.UUID
    noc: str | None
    pn: str | None
    ncage: str | None
    nombre: str
    origin: str


# ── parts ────────────────────────────────────────────────────────────────


class PartIn(StrictModel):
    cop: str = Field(min_length=1, max_length=40)
    alp: str | None = _Short
    quantity: _Number = None
    part_name: str | None = Field(default=None, max_length=200)
    # The part: chosen (article_id) or found by NOC, P/N + NCAGE, name.
    article_id: uuid.UUID | None = None
    noc: str | None = _Short
    pn: str | None = Field(default=None, max_length=32)
    ncage: str | None = Field(default=None, max_length=20)


class PartUpdate(StrictModel):
    """Only what is sent changes; the part is linked again when its NOC,
    P/N, NCAGE or article_id is sent."""

    version: int
    cop: str | None = Field(default=None, min_length=1, max_length=40)
    alp: str | None = _Short
    quantity: _Number = None
    part_name: str | None = Field(default=None, max_length=200)
    article_id: uuid.UUID | None = None
    noc: str | None = _Short
    pn: str | None = Field(default=None, max_length=32)
    ncage: str | None = Field(default=None, max_length=20)


class PartOut(BaseModel):
    id: uuid.UUID
    parent_article_id: uuid.UUID
    cop: str
    alp: str
    quantity: str | None
    part_name: str | None
    article: ArticleBrief | None
    source: str
    observations: list[dict[str, Any]]
    observation_codes: list[str]
    # The ALP of its COP (an ALP alone, OP-006, offers going back to 00).
    alternative: bool
    version: int
    updated_at: datetime


class CufPartOut(PartOut):
    """A part in the CUF's "Tabla de partes": its parent and the parent's
    positions in the CONFUNFIS, and its total in the CUF."""

    parent: ArticleBrief
    parent_positions: list[str]
    total: str | None


# ── functional products ──────────────────────────────────────────────────


class ProductIn(StrictModel):
    designation: str = Field(min_length=1, max_length=200)
    pol_code: str | None = _Short
    nae: str | None = Field(default=None, max_length=1)
    noc: str | None = _Short
    supply_unit: str | None = _Short
    # Empty or "N/A": in bulk.
    quantity: _Number = None
    unit: str | None = _Short


class ProductUpdate(StrictModel):
    version: int
    designation: str | None = Field(default=None, min_length=1, max_length=200)
    pol_code: str | None = _Short
    nae: str | None = Field(default=None, max_length=1)
    noc: str | None = _Short
    supply_unit: str | None = _Short
    quantity: _Number = None
    unit: str | None = _Short


class ProductOut(BaseModel):
    id: uuid.UUID
    designation: str
    pol_code: str | None
    pol_description: str | None
    nae: str | None
    noc: str | None
    article: ArticleBrief | None
    supply_unit: str | None
    quantity: str | None
    unit: str | None
    source: str
    observations: list[dict[str, Any]]
    observation_codes: list[str]
    version: int
    updated_at: datetime


# ── extra functions ──────────────────────────────────────────────────────


class ExtraFunctionIn(StrictModel):
    position_id: uuid.UUID
    sns: str = Field(min_length=1, max_length=40)
    criterion: str = Field(min_length=1, max_length=40)
    comment: str | None = Field(default=None, max_length=1000)


class ExtraFunctionUpdate(StrictModel):
    version: int
    sns: str | None = Field(default=None, min_length=1, max_length=40)
    criterion: str | None = Field(default=None, min_length=1, max_length=40)
    comment: str | None = Field(default=None, max_length=1000)


class RowRef(BaseModel):
    """A CONFUNFIS row as another list shows it."""

    id: uuid.UUID
    position: str
    name: str | None
    deleted: bool = False


class ExtraFunctionOut(BaseModel):
    id: uuid.UUID
    row: RowRef
    sns: str
    sns_name: str | None
    criterion: str
    comment: str | None
    source: str
    version: int
    updated_at: datetime


# ── incompatibilities ────────────────────────────────────────────────────


class IncompatibilityIn(StrictModel):
    row_a_id: uuid.UUID
    row_b_id: uuid.UUID
    kind: Literal["excluye", "requiere"]
    reason: str = Field(min_length=1, max_length=1000)


class IncompatibilityUpdate(StrictModel):
    version: int
    kind: Literal["excluye", "requiere"] | None = None
    reason: str | None = Field(default=None, min_length=1, max_length=1000)


class IncompatibilityOut(BaseModel):
    id: uuid.UUID
    row_a: RowRef
    row_b: RowRef
    kind: str
    reason: str
    source: str
    observations: list[dict[str, Any]]
    observation_codes: list[str]
    version: int
    updated_at: datetime
