"""One app version: backend/pyproject.toml and package.json agree."""
import json
from pathlib import Path

from app.version import aacf_version, app_version

REPO = Path(__file__).resolve().parents[3]


def test_backend_and_frontend_versions_are_the_same():
    package = json.loads((REPO / "package.json").read_text(encoding="utf-8"))
    assert app_version() == package["version"]


def test_aacf_version_is_the_copys():
    assert aacf_version() == (REPO / "aacf" / "VERSION").read_text(encoding="utf-8").strip()


def test_missing_aacf_version_file_is_none_not_invented(monkeypatch, tmp_path):
    from app.core.config import get_settings

    monkeypatch.setenv("AACF_VERSION_FILE", str(tmp_path / "missing" / "VERSION"))
    get_settings.cache_clear()
    try:
        assert aacf_version() is None
    finally:
        get_settings.cache_clear()
