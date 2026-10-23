import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import StrictModel
from app.schemas.materials import NCAGE_PATTERN, NOC_PATTERN, normalize_code


class VersionBrief(BaseModel):
    id: uuid.UUID
    number: int
    label: str
    is_active: bool


class MaterialLink(BaseModel):
    id: uuid.UUID
    name: str


class CufSubcategory(BaseModel):
    code: str
    name: str
    category_code: str
    category_name: str
    # Its SNS in the CUF's catalog version.
    sns_count: int


class CufOut(BaseModel):
    """The CUF side of a material: catalog version, subcategories, its
    normalized configuration in figures, and its family of variants."""

    material_id: uuid.UUID
    version: int
    catalog_version: VersionBrief | None
    subcategories: list[CufSubcategory]
    sns_count: int
    levels: dict[str, int]
    copied_from: MaterialLink | None
    variants: list[MaterialLink]


class SubcategoriesIn(StrictModel):
    # The material's version (the change bumps it).
    version: int
    codes: list[Annotated[str, Field(pattern=r"^[0-9]{4}$")]] = Field(max_length=200)


class CatalogVersionChange(StrictModel):
    version: int
    catalog_version_id: uuid.UUID
    # The person saw the impact and agrees (HR9).
    confirm: bool


class ImpactOut(BaseModel):
    added: list[str]
    removed: list[str]
    subcategories_missing: list[str]
    sns_before: int
    sns_after: int


class NormalizedNode(BaseModel):
    sns: str
    name: str
    level: str
    description_pending: bool
    child_count: int
    origins: list[str]


class NormalizedSearchPage(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[NormalizedNode]


class CopyIn(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    noc: str | None = Field(default=None, pattern=NOC_PATTERN)
    part_number: str | None = Field(default=None, min_length=1, max_length=32)
    ncage: str | None = Field(default=None, pattern=NCAGE_PATTERN)
    copy_members: bool = False

    @field_validator("noc", "ncage", mode="before")
    @classmethod
    def _normalize_codes(cls, value: object) -> object:
        return normalize_code(value)


class SnsRequestIn(StrictModel):
    proposed_sns: str | None = Field(default=None, pattern=r"^[A-Z0-9]{6}$")
    parent_sns: str | None = Field(default=None, pattern=r"^[A-Z0-9]{6}$")
    name: str = Field(min_length=1, max_length=300)
    function: str = Field(default="", max_length=4000)
    justification: str = Field(min_length=1, max_length=4000)

    @field_validator("proposed_sns", "parent_sns", mode="before")
    @classmethod
    def _normalize_sns(cls, value: object) -> object:
        return normalize_code(value)


class SnsRequestUpdate(SnsRequestIn):
    version: int


class SnsRequestStep(StrictModel):
    version: int


class SnsRequestResolve(StrictModel):
    version: int
    decision: str = Field(pattern="^(aceptada|rechazada)$")
    response: str = Field(min_length=1, max_length=4000)


class SnsRequestOut(BaseModel):
    id: uuid.UUID
    proposed_sns: str | None
    parent_sns: str | None
    name: str
    function: str
    justification: str
    state: str
    response: str | None
    created_by: str | None
    resolved_by: str | None
    created_at: datetime
    sent_at: datetime | None
    resolved_at: datetime | None
    version: int
