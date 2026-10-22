"""Parameters are read as defaults deep-merged with the stored row (HR0/HR10)."""
import uuid

import pytest
from sqlalchemy import delete

from app.models import AppParameter
from app.services.parameters import PARAMETER_DEFAULTS, UnknownParameterError, get_parameter

DEFAULTS = {"demo": {"grid": {"page_size": 25, "columns": ["sns", "co"]}, "export": {"sheet": "CONFUNFIS"}}}


async def test_without_a_row_the_defaults_are_returned(db):
    key = f"test.{uuid.uuid4()}"
    assert await get_parameter(db, key, {key: DEFAULTS["demo"]}) == DEFAULTS["demo"]


async def test_stored_row_is_deep_merged_over_the_defaults(db):
    key = f"test.{uuid.uuid4()}"
    db.add(AppParameter(key=key, value={"grid": {"page_size": 50}}, description="test"))
    await db.commit()
    try:
        value = await get_parameter(db, key, {key: DEFAULTS["demo"]})
        assert value == {"grid": {"page_size": 50, "columns": ["sns", "co"]}, "export": {"sheet": "CONFUNFIS"}}
    finally:
        await db.execute(delete(AppParameter).where(AppParameter.key == key))
        await db.commit()


async def test_unknown_key_is_an_error_not_an_empty_value(db):
    with pytest.raises(UnknownParameterError):
        await get_parameter(db, f"test.{uuid.uuid4()}", {})


def test_the_registry_starts_empty():
    """E00 declares no parameters; each encargo adds its own (with its
    Settings section, HR0)."""
    assert PARAMETER_DEFAULTS == {}
