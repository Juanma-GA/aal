"""Configurable parameters (HR0/HR10): the code's defaults deep-merged with
what app_parameter stores.

Every parameter has its defaults in PARAMETER_DEFAULTS (the key is
app_parameter.key). A read always returns deep_merge(defaults, stored): a
row only needs the keys that differ, and a key the code adds later is
there with its default without touching the database. A key the code does
not declare is an error, never an empty dict (HR7).

Each encargo that adds a parameter adds its defaults here and shows it in
Settings (HR0): for now Settings -> Parámetros lists them read-only (E01);
editing them comes later.
"""

from collections.abc import Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.merge import deep_merge
from app.models import AppParameter

PARAMETER_DEFAULTS: dict[str, dict[str, Any]] = {
    # Sessions, passwords and the login limit (E01, D4).
    "auth": {
        # Lifetime of an access token (kept in memory by the browser).
        "access_token_minutes": 15,
        # Lifetime of a refresh token (HttpOnly cookie); each refresh
        # replaces it with a new one of the same lifetime.
        "refresh_token_days": 7,
        "password": {
            # Minimum length of a password a person chooses. bcrypt's own
            # limit (72 bytes) is the maximum, a fact, not a parameter.
            "min_length": 12,
        },
        # Length of the temporary password an admin hands over.
        "temporary_password_length": 16,
        "login_limit": {
            # Failed logins counted over the last `window_minutes`; at the
            # limit, the login is refused until the window passes.
            "window_minutes": 15,
            "max_failures_per_email": 5,
            "max_failures_per_ip": 20,
        },
    },
    # The material's Panel (E02).
    "panel": {
        # Latest actions of the material shown in "Actividad reciente".
        "activity_items": 10,
    },
    # Excel imports (E03, app/io_excel): limits of an uploaded workbook,
    # checked before it is read (a zip bomb never gets expanded).
    "import": {
        "max_file_mb": 10,
        # Sum of the sizes of the files inside the .xlsx (a zip).
        "max_uncompressed_mb": 100,
        "max_rows": 20000,
        # An analysis still running after this long is taken as dead (the
        # process stopped) and marked failed the next time it is read.
        "stale_minutes": 30,
    },
    # The normalized functional configuration (E10): search and diff pages.
    "catalog": {
        "page_size": 50,
        "max_page_size": 200,
    },
    # The article master (E12): a page of its list (virtualized) and of the
    # grid's batch.
    "articles": {
        "page_size": 200,
        "max_page_size": 1000,
        # Rows of one save of the grid (it sends more in several).
        "max_batch_rows": 200,
        # A revalidation of every article still queued or running after this
        # long was killed (a restart) and is marked failed (E13).
        "revalidation_stale_minutes": 30,
    },
    # The CONFUNFIS (E13): the ranges of CO (component) and AL (alternative,
    # 00 = none) a row is checked against, and a page of its table.
    "confunfis": {
        "co": {"min": 1, "max": 99},
        "al": {"min": 0, "max": 99},
        # The parts table of an article (E14, §9.1.10): COP and ALP.
        "cop": {"min": 1, "max": 99},
        "alp": {"min": 0, "max": 99},
        # The largest QTY a row takes, and its decimals (a bigger one cannot be stored).
        "qty": {"max": 1000000, "decimals": 6},
        "page_size": 200,
        "max_page_size": 1000,
        # The empty template for a subcontractor (E15): rows with dropdown lists, and the largest
        # configuration whose SNS still get one (Excel slows down with a longer list).
        "template": {"list_rows": 2000, "max_sns_list": 5000},
    },
    # The interface (E12): the sidebar's width in pixels, dragged by its edge.
    "ui": {
        "sidebar_width": {"min": 200, "max": 480, "default": 256},
        # The detail panel docked on the right (E15): its width in pixels, dragged by its edge.
        "detail_panel_width": {"min": 320, "max": 960, "default": 480},
    },
    # Settings -> Auditoría.
    "audit": {
        "page_size": 50,
        "max_page_size": 200,
    },
}


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
