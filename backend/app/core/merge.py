"""deep_merge (HR10): nested configuration is merged key by key, never
replaced whole by a shallow `{**a, **b}`."""

from collections.abc import Mapping
from copy import deepcopy
from typing import Any


def deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    """A new dict with `override` merged into `base`, at every depth.

    - A key in both whose two values are mappings is merged recursively, so
      a nested key that `override` does not mention keeps `base`'s value.
    - Any other value in `override` (a scalar, a list, None) replaces
      `base`'s. Lists are values, not merged element by element.
    - Neither argument is modified; the result shares no mutable object
      with them.

    Args:
        base: The defaults.
        override: The values that win (e.g. what the database stores).

    Returns:
        The merged dict.
    """
    merged: dict[str, Any] = deepcopy(dict(base))
    for key, value in override.items():
        current = merged.get(key)
        if isinstance(current, Mapping) and isinstance(value, Mapping):
            merged[key] = deep_merge(current, value)
        else:
            merged[key] = deepcopy(value)
    return merged
