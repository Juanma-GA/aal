import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class CatalogVersionOut(BaseModel):
    id: uuid.UUID
    number: int
    label: str
    file_name: str
    imported_at: datetime
    imported_by: str | None
    is_active: bool
    counts: dict[str, int]
    notes: str
    version: int


class SubcategoryOut(BaseModel):
    code: str
    sub_code: str
    name: str
    sns_count: int


class CategoryOut(BaseModel):
    code: str
    name: str
    subcategories: list[SubcategoryOut]


class CategoriesOut(BaseModel):
    categories: list[CategoryOut]
    # Rows without category nor subcategory (CN-004).
    uncategorized_rows: int


class TreeNode(BaseModel):
    sns: str
    name: str
    level: str
    description_pending: bool
    child_count: int


class SearchHit(BaseModel):
    sns: str
    name: str
    level: str
    description_pending: bool
    subcategories: list[str]


class SearchPage(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[SearchHit]


class SnsLink(BaseModel):
    sns: str
    name: str
    level: str


class ExtraName(BaseModel):
    name: str
    origin: str


class SnsAppearance(BaseModel):
    """A row where the SNS appears: its subcategory (None for CN-004),
    the level and name the row declares."""

    subcategory_code: str | None
    subcategory_name: str | None
    category_name: str | None
    declared_level: str
    name: str
    row_number: int


class SnsDetail(BaseModel):
    sns: str
    name: str
    description: str
    description_pending: bool
    level: str
    declared_levels: list[str]
    parent_sns: str | None
    parent: SnsLink | None
    children: list[SnsLink]
    extra_names: list[ExtraName]
    appearances: list[SnsAppearance]


class WarningsOut(BaseModel):
    counts: dict[str, int]
    items: list[dict[str, Any]]


class DiffItem(BaseModel):
    sns: str
    change: str  # new, modified, removed
    changes: list[dict[str, str]]
    name: str


class DiffOut(BaseModel):
    summary: dict[str, int]
    total: int
    page: int
    page_size: int
    items: list[DiffItem]
