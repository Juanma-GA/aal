"""The versions GET /api/version answers: the app's (backend/pyproject.toml,
the same as package.json's -- tests/unit/test_version.py) and the AACF
copy's (aacf/VERSION, AACF_VERSION_FILE)."""

import logging
import tomllib
from functools import lru_cache

from app.core.config import BACKEND_DIR, backend_path, get_settings

logger = logging.getLogger(__name__)


@lru_cache
def app_version() -> str:
    """The app's version, from backend/pyproject.toml."""
    with (BACKEND_DIR / "pyproject.toml").open("rb") as fh:
        return tomllib.load(fh)["project"]["version"]


def aacf_version() -> str | None:
    """The AACF copy's version, or None when its VERSION file is not there
    (a server deployed without the aacf/ folder). None is shown as "not
    available", never as a made-up version; the miss is logged."""
    path = backend_path(get_settings().aacf_version_file)
    try:
        return path.read_text(encoding="utf-8").strip() or None
    except FileNotFoundError:
        logger.warning("AACF version file not found: %s (AACF_VERSION_FILE)", path)
        return None
