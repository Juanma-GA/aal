import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import StrictModel


class UserMaterialOut(BaseModel):
    material_id: uuid.UUID
    material_name: str
    role: str


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    is_admin: bool
    is_active: bool
    must_change_password: bool
    created_at: datetime
    deleted_at: datetime | None
    version: int
    materials: list[UserMaterialOut] = []


class UserCreate(StrictModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=200)
    is_admin: bool = False


class UserUpdate(StrictModel):
    version: int
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    is_admin: bool | None = None
    is_active: bool | None = None


class UserCreated(BaseModel):
    user: UserOut
    # Shown once to the admin, never stored or logged.
    temporary_password: str


class PasswordReset(BaseModel):
    user: UserOut
    temporary_password: str
