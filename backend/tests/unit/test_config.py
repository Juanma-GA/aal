import pytest
from pydantic import ValidationError

from _testdb import APP_DEFAULT_DATABASE_URL
from app.core.config import Settings


def test_cors_wildcard_is_refused(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", '["*"]')
    with pytest.raises(ValidationError, match="never"):
        Settings(_env_file=None)


def test_cors_wildcard_among_real_origins_is_refused(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", '["http://localhost:5173", " * "]')
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_unknown_environment_is_refused(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "staging")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_testdb_knows_the_apps_default_database(monkeypatch):
    """tests/_testdb.py repeats the app's default DATABASE_URL (it must not
    import the app); both must stay the same."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert Settings(_env_file=None).database_url == APP_DEFAULT_DATABASE_URL
