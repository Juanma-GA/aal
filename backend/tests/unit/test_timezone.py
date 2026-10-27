"""The documents' time zone (E16, app/core/timezone.py) as on Windows:
no zone database in the system. With the `tzdata` package (in the
lockfiles) it still resolves; without it, a clear error at startup, never
on import (the backend must at least start to say so) and never a 500
halfway through an export (HR7)."""

import importlib
import sys
import zoneinfo
from datetime import UTC, datetime

import pytest

from app.core import timezone
from app.core.config import get_settings


@pytest.fixture
def no_system_zones(monkeypatch):
    """Windows: zoneinfo finds no zone database of the system."""
    zoneinfo.reset_tzpath(to=[])
    zoneinfo.ZoneInfo.clear_cache()
    timezone.zone.cache_clear()
    yield
    zoneinfo.reset_tzpath()
    zoneinfo.ZoneInfo.clear_cache()
    timezone.zone.cache_clear()
    get_settings.cache_clear()


def _without_tzdata(monkeypatch):
    for name in [m for m in sys.modules if m == "tzdata" or m.startswith("tzdata.")]:
        monkeypatch.delitem(sys.modules, name)
    monkeypatch.setitem(sys.modules, "tzdata", None)  # import tzdata -> ImportError


def test_the_tzdata_package_is_enough(no_system_zones):
    zone = timezone.zone()
    assert zone.key == "Europe/Madrid"
    from app.services.validation_report import when

    # 12:00 UTC on a summer day is 14:00 in Madrid.
    assert when(datetime(2026, 7, 1, 12, 0, tzinfo=UTC)) == "01/07/2026 14:00"


def test_without_any_zone_data_the_error_is_clear_and_not_on_import(no_system_zones, monkeypatch):
    _without_tzdata(monkeypatch)
    import app.services.validation_report as report

    importlib.reload(report)  # importing never resolves the zone
    with pytest.raises(RuntimeError, match="zona horaria «Europe/Madrid».*tzdata"):
        timezone.check()


def test_the_zone_is_a_setting(no_system_zones, monkeypatch):
    monkeypatch.setenv("TIMEZONE", "America/New_York")
    get_settings.cache_clear()
    assert timezone.zone().key == "America/New_York"
    monkeypatch.setenv("TIMEZONE", "Mars/Olympus")
    get_settings.cache_clear()
    timezone.zone.cache_clear()
    with pytest.raises(RuntimeError, match="Mars/Olympus"):
        timezone.check()
