"""Baselines and change authorizations (E17)."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import StrictModel

BaselineState = Literal["en_revision", "revisada", "rechazada", "retirada"]
AuthorizationState = Literal["solicitada", "aprobada", "rechazada", "cerrada"]


class RunBrief(BaseModel):
    id: uuid.UUID
    state: Literal["red", "amber", "green", "none"]
    blocking: int
    warnings: int
    accepted: int
    at: datetime


class BaselineOut(BaseModel):
    id: uuid.UUID
    number: int
    scope: str
    state: BaselineState
    created_at: datetime
    created_by: uuid.UUID | None
    created_by_name: str | None
    reviewed_at: datetime | None
    reviewed_by_name: str | None
    review_comment: str | None
    validation: RunBrief | None
    rows: int
    snapshot_hash: str
    version: int


class AuthorizationOut(BaseModel):
    id: uuid.UUID
    code: str
    number: int
    kind: str
    description: str
    reason: str
    state: AuthorizationState
    requested_at: datetime
    requested_by: uuid.UUID | None
    requested_by_name: str | None
    decided_at: datetime | None
    decided_by_name: str | None
    decision_comment: str | None
    closed_at: datetime | None
    closed_in_baseline: int | None
    changes: int
    version: int


class ConfigurationState(BaseModel):
    """The CUF's configuration state: the Panel and the CONFUNFIS band."""

    reviewed: BaselineOut | None
    in_review: BaselineOut | None
    changes_since: int
    open_authorizations: int
    usable_authorizations: list[AuthorizationOut]
    # free: no baseline; locked: one in review (read-only); authorization: needs an approved one.
    edit: Literal["free", "locked", "authorization"]


class VersionIn(StrictModel):
    version: int


class ReviewIn(StrictModel):
    version: int
    comment: str | None = Field(default=None, max_length=2000)


class AuthorizationIn(StrictModel):
    kind: str = Field(min_length=1, max_length=40)
    description: str = Field(min_length=1, max_length=2000)
    reason: str = Field(min_length=1, max_length=2000)


class FieldChange(BaseModel):
    field: str
    before: str
    after: str


class AuthorizationRef(BaseModel):
    id: uuid.UUID
    code: str


class DiffEntry(BaseModel):
    entity: Literal["row", "product", "extra", "incompatibility", "article", "part"]
    id: str
    label: str
    change: Literal["added", "removed", "modified"]
    fields: list[FieldChange]
    authorizations: list[AuthorizationRef]


class DiffOut(BaseModel):
    before: str
    after: str
    entries: list[DiffEntry]


class AuthorizationChangeOut(BaseModel):
    entity_type: str
    entity_id: str
    action: str
    label: str
    at: datetime
    by: str | None
