import uuid
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import StrictModel


class LoginRequest(StrictModel):
    # A plain string, not EmailStr: a malformed address is just a failed
    # login, answered like any other.
    email: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=1000)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class MeOut(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    is_admin: bool
    must_change_password: bool
    ui_preferences: dict[str, Any]


class PasswordChange(StrictModel):
    current_password: str = Field(min_length=1, max_length=1000)
    new_password: str = Field(min_length=1, max_length=1000)


class UiPreferencesPatch(StrictModel):
    """The interface state kept on the server (HR1). Only known keys; a key
    sent is deep-merged over what is stored (HR10), a key not sent is kept."""

    active_material_id: uuid.UUID | None = None
