import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import StrictModel

# NOC: 13 characters; NCAGE: 5 (NT 10/17 §9.1.3). Upper-case letters and digits.
NOC_PATTERN = r"^[0-9A-Z]{13}$"
NCAGE_PATTERN = r"^[0-9A-Z]{5}$"


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


class MaterialFields(StrictModel):
    noc: str | None = Field(default=None, pattern=NOC_PATTERN)
    name: str = Field(min_length=1, max_length=200)
    part_number: str | None = Field(default=None, min_length=1, max_length=32)
    ncage: str | None = Field(default=None, pattern=NCAGE_PATTERN)
    description: str = Field(default="", max_length=4000)


class MaterialCreate(MaterialFields):
    pass


class MaterialUpdate(StrictModel):
    version: int
    noc: str | None = Field(default=None, pattern=NOC_PATTERN)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    part_number: str | None = Field(default=None, min_length=1, max_length=32)
    ncage: str | None = Field(default=None, pattern=NCAGE_PATTERN)
    description: str | None = Field(default=None, max_length=4000)


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
