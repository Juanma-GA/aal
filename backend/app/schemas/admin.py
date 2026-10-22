import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class RoleOut(BaseModel):
    code: str


class PermissionOut(BaseModel):
    code: str
    area: str


class RoleMatrix(BaseModel):
    roles: list[RoleOut]
    permissions: list[PermissionOut]
    matrix: dict[str, list[str]]


class AuditEntry(BaseModel):
    id: uuid.UUID
    created_at: datetime
    user_id: uuid.UUID | None
    user_email: str | None
    action: str
    entity_type: str
    entity_id: str
    material_id: uuid.UUID | None
    material_name: str | None
    before: Any | None
    after: Any | None
    ip: str | None


class AuditPage(BaseModel):
    items: list[AuditEntry]
    total: int
    page: int
    page_size: int


class AuditFacets(BaseModel):
    actions: list[str]
    entity_types: list[str]


class ParameterOut(BaseModel):
    key: str
    value: dict[str, Any]
