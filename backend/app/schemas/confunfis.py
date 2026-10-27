"""The CONFUNFIS of a material (E13): what the API reads and writes."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, Field

from app.schemas.common import StrictModel
from app.schemas.confunfis_extras import ArticleBrief, CufPartOut, ExtraFunctionOut, IncompatibilityOut

_Short = Field(default=None, max_length=40)


class RowIn(StrictModel):
    sns: str = Field(min_length=1, max_length=40)
    co: str = Field(min_length=1, max_length=40)
    al: str | None = _Short
    qty: Annotated[str, Field(max_length=40)] | int | float | Decimal | None = None
    # The article: chosen (article_id) or found by NOC, P/N + NCAGE, name.
    article_id: uuid.UUID | None = None
    noc: str | None = _Short
    pn: str | None = Field(default=None, max_length=32)
    ncage: str | None = Field(default=None, max_length=20)
    article_name: str | None = Field(default=None, max_length=200)
    function_text: str | None = Field(default=None, max_length=1000)
    ct_sigle: str | None = Field(default=None, max_length=1)
    cs_sns: str | None = _Short
    cs_co: str | None = _Short
    cs_al: str | None = _Short


class RowUpdate(StrictModel):
    """Only what is sent changes; the article is linked again when its NOC,
    P/N, NCAGE or article_id is sent."""

    version: int
    sns: str | None = Field(default=None, min_length=1, max_length=40)
    co: str | None = Field(default=None, min_length=1, max_length=40)
    al: str | None = _Short
    qty: Annotated[str, Field(max_length=40)] | int | float | Decimal | None = None
    article_id: uuid.UUID | None = None
    noc: str | None = _Short
    pn: str | None = Field(default=None, max_length=32)
    ncage: str | None = Field(default=None, max_length=20)
    article_name: str | None = Field(default=None, max_length=200)
    function_text: str | None = Field(default=None, max_length=1000)
    ct_sigle: str | None = Field(default=None, max_length=1)
    cs_sns: str | None = _Short
    cs_co: str | None = _Short
    cs_al: str | None = _Short


class VersionIn(StrictModel):
    version: int


class AlternativeCsIn(StrictModel):
    version: int
    cs_sns: str = Field(min_length=1, max_length=40)
    cs_co: str = Field(min_length=1, max_length=40)
    cs_al: str = Field(min_length=1, max_length=40)


class MaterialBrief(BaseModel):
    id: uuid.UUID
    name: str


class RowOut(BaseModel):
    id: uuid.UUID
    sns: str
    co: str
    al: str
    qty: str | None
    sns_name: str | None
    article: ArticleBrief | None
    article_name: str | None
    function_text: str | None
    ct_sigle: str | None
    cs_sns: str | None
    cs_co: str | None
    cs_al: str | None
    source: str
    observations: list[dict[str, Any]]
    observation_codes: list[str]
    # Computed: the hueco's total in the CUF (None: orphan, cycle, no QTY).
    total: str | None
    orphan: str | None
    alternative: bool
    cs_alternative: bool
    child_count: int
    # The CUF of another material the user may open (§9.1.12); one they may
    # not open stays unknown, as a 404.
    is_mounted: bool
    mounted: MaterialBrief | None
    # E14: its extra functions (a multifunction component) and incompatibilities.
    extra_function_count: int = 0
    incompatibility_count: int = 0
    version: int
    updated_at: datetime


class RowPage(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[RowOut]


class TreeLevel(BaseModel):
    """The rows hanging from `parent` (a position "SNS CO AL"); at the
    root, also the CUF's own row, the orphans and the huecos on a cycle."""

    parent: str
    items: list[RowOut]
    root: RowOut | None = None
    orphans: list[RowOut] = []
    cycles: list[str] = []


class ChainStep(BaseModel):
    qty: str | None
    sns: str | None


class RowDetail(RowOut):
    parents: list[RowOut]
    children: list[RowOut]
    chains: list[list[ChainStep]]
    history: list[dict[str, Any]]
    # The distinct AL of its hueco (E14: removing one may leave a single AL).
    hueco_als: list[str] = []
    # E14: what hangs from the row, and the parts of its article (with their total in the CUF).
    extra_functions: list[ExtraFunctionOut] = []
    incompatibilities: list[IncompatibilityOut] = []
    parts: list[CufPartOut] = []


class PathStep(BaseModel):
    id: uuid.UUID
    position: str


class SearchHit(BaseModel):
    row: RowOut
    # The rows from the CUF down to the hit's CS, to open the tree there.
    path: list[PathStep]


class SearchResult(BaseModel):
    total: int
    hits: list[SearchHit]


class FunctionalNode(BaseModel):
    sns: str
    name: str
    level: str
    description_pending: bool
    child_count: int
    row_count: int
    # Rows in this SNS and every SNS below it in the configuration.
    rows_below: int
    # E14: extra functions of rows elsewhere that cover this SNS (and below it).
    extra_count: int = 0
    extras_below: int = 0


class FunctionalLevel(BaseModel):
    items: list[FunctionalNode]
    # At the top only: the rows whose SNS is not in the configuration.
    outside: list[RowOut] = []


class Summary(BaseModel):
    rows: int
    positions: int
    huecos: int
    sns_covered: int
    sns_in_config: int
    with_observations: int
    by_observation: dict[str, int]
    # E16: the rows' findings by the severity their rules have now (errors block the delivery).
    errors: int = 0
    warnings: int = 0
    # E14
    sns_covered_by_extra: int = 0
    products: int = 0
    multifunction_rows: int = 0
    incompatibility_rows: int = 0


class NextSlot(BaseModel):
    co: str
    al: str
