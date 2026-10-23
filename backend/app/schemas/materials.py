import uuid
from datetime import datetime

import re

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import StrictModel

# NOC: 13 characters; NCAGE: 5 (NT 10/17 §9.1.3). Upper-case letters and digits.
NOC_PATTERN = r"^[0-9A-Z]{13}$"
NCAGE_PATTERN = r"^[0-9A-Z]{5}$"


def format_problems(noc: str | None, ncage: str | None) -> list[str]:
    """The identifiers of a stored material that do not have their format
    (one saved before E10 checked it): "noc", "ncage". Never corrected
    silently: the list shows them with a warning."""
    problems = []
    if noc is not None and not re.fullmatch(NOC_PATTERN, noc):
        problems.append("noc")
    if ncage is not None and not re.fullmatch(NCAGE_PATTERN, ncage):
        problems.append("ncage")
    return problems


def _code(value: object) -> object:
    """NOC and NCAGE as they are checked: upper case, no spaces at all;
    empty is no value."""
    if isinstance(value, str):
        value = re.sub(r"\s+", "", value).upper()
        return value or None
    return value


class MaterialOut(BaseModel):
    id: uuid.UUID
    noc: str | None
    name: str
    part_number: str | None
    ncage: str | None
    description: str
    created_at: datetime
    updated_at: datetime
    version: int
    # The caller's role on it (None: an admin who is not a member) and
    # what they may do (the hook useMaterialPermission reads it).
    role: str | None
    permissions: list[str]
    # Stored identifiers without their format ("noc", "ncage").
    format_problems: list[str]


class MaterialFields(StrictModel):
    noc: str | None = Field(default=None, pattern=NOC_PATTERN)
    name: str = Field(min_length=1, max_length=200)
    part_number: str | None = Field(default=None, min_length=1, max_length=32)
    ncage: str | None = Field(default=None, pattern=NCAGE_PATTERN)
    description: str = Field(default="", max_length=4000)

    @field_validator("noc", "ncage", mode="before")
    @classmethod
    def _normalize_codes(cls, value: object) -> object:
        return _code(value)


class MaterialCreate(MaterialFields):
    pass


class MaterialUpdate(StrictModel):
    version: int
    noc: str | None = Field(default=None, pattern=NOC_PATTERN)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    part_number: str | None = Field(default=None, min_length=1, max_length=32)
    ncage: str | None = Field(default=None, pattern=NCAGE_PATTERN)
    description: str | None = Field(default=None, max_length=4000)

    @field_validator("noc", "ncage", mode="before")
    @classmethod
    def _normalize_codes(cls, value: object) -> object:
        return _code(value)


class MemberOut(BaseModel):
    """A member of the team. user_id, email and assigned_at only for an admin."""

    display_name: str
    role: str
    user_id: uuid.UUID | None = None
    email: str | None = None
    assigned_at: datetime | None = None


class ActivityEntry(BaseModel):
    """A recent action on a material: who (None: the system or a removed
    user), what and when -- no data before or after."""

    created_at: datetime
    action: str
    entity_type: str
    user_name: str | None


class MemberAssign(StrictModel):
    role: str = Field(min_length=1, max_length=50)
