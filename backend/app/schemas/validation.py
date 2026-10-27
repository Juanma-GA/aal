"""The NT 10/17 validator's API (E16)."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.common import StrictModel

Severity = Literal["bloqueante", "aviso", "desactivada"]


class RuleOut(BaseModel):
    code: str
    scope: str
    ref: str
    active: bool
    severity: Severity
    # The catalog's, for "Restablecer".
    default_severity: Severity
    params: dict[str, Any]
    help: str | None
    version: int
    updated_at: datetime


class RuleUpdate(StrictModel):
    version: int
    active: bool | None = None
    severity: Severity | None = None
    params: dict[str, Any] | None = Field(default=None, max_length=20)
    help: str | None = Field(default=None, max_length=2000)


class FindingOut(BaseModel):
    id: uuid.UUID
    rule_code: str
    severity: str
    scope: str
    entity_type: str
    entity_id: str
    problem: str
    params: dict[str, Any]
    field: str | None
    row_id: str | None
    location: str
    found: str | None
    accepted: bool
    justification: str | None
    accepted_by: str | None
    accepted_at: datetime | None


class RuleCount(BaseModel):
    code: str
    severity: str
    ref: str
    findings: int
    accepted: int


class ValidationOut(BaseModel):
    """The latest validation of a CUF: its traffic light and findings (none yet: state "none")."""

    state: Literal["red", "amber", "green", "none"]
    outdated: bool
    outdated_data: bool
    outdated_rules: bool
    run_id: uuid.UUID | None = None
    at: datetime | None = None
    by: str | None = None
    trigger: str | None = None
    seconds: float | None = None
    blocking: int = 0
    warnings: int = 0
    accepted: int = 0
    by_rule: list[RuleCount] = []
    findings: list[FindingOut] = []
    # Why "Exportar para entrega" is refused now (empty: it may go).
    delivery_problems: list[dict[str, Any]] = []


class AcceptIn(StrictModel):
    justification: str = Field(min_length=3, max_length=2000)
