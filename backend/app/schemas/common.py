from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    """Request bodies: an unexpected field is refused, never ignored
    (AACF security.mdc), and strings are trimmed."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
