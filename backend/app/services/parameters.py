"""Configurable parameters (HR0/HR10): the code's defaults deep-merged with
what app_parameter stores.

Every parameter has its defaults in PARAMETER_DEFAULTS (the key is
app_parameter.key). A read always returns deep_merge(defaults, stored): a
row only needs the keys that differ, and a key the code adds later is
there with its default without touching the database. A key the code does
not declare is an error, never an empty dict (HR7).

The registry starts empty: each encargo that adds a parameter adds its
defaults here and its section in Settings (HR0).
"""

from collections.abc import Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.merge import deep_merge
from app.models import AppParameter

PARAMETER_DEFAULTS: dict[str, dict[str, Any]] = {}


class UnknownParameterError(KeyError):
    """A parameter key the code declares no defaults for."""


async def get_parameter(
    db: AsyncSession, key: str, defaults: Mapping[str, Mapping[str, Any]] | None = None
) -> dict[str, Any]:
    """The value of parameter `key`: its defaults with the stored row
    deep-merged over them.

    Args:
        db: A session.
        key: The parameter's key.
        defaults: The registry to read the defaults from (PARAMETER_DEFAULTS
            unless given; the tests pass their own).

    Returns:
        The merged value.

    Raises:
        UnknownParameterError: `key` has no defaults in the registry.
    """
    registry = PARAMETER_DEFAULTS if defaults is None else defaults
    if key not in registry:
        raise UnknownParameterError(key)
    stored = await db.scalar(select(AppParameter.value).where(AppParameter.key == key))
    if stored is None:
        return deep_merge(registry[key], {})
    if not isinstance(stored, Mapping):
        raise TypeError(f"app_parameter {key!r} holds a {type(stored).__name__}, not an object")
    return deep_merge(registry[key], stored)
