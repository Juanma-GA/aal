from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


def backend_path(value: str) -> Path:
    """A path setting as a real path: relative ones are taken from backend/,
    whatever the process's working directory."""
    path = Path(value)
    return path if path.is_absolute() else BACKEND_DIR / path


class Settings(BaseSettings):
    """Backend configuration, every value overridable from the environment
    or backend/.env. Nothing tunable lives elsewhere in the code (HR8);
    backend/.env.example lists every field with its default
    (tests/unit/test_env_example.py keeps both in step).
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Environment ---
    # "development" or "production".
    environment: str = "development"
    # Level of the JSON log on stderr (app/core/logging.py).
    log_level: str = "INFO"

    # --- Database ---
    database_url: str = "postgresql+asyncpg://aal:aal@localhost:5432/aal"
    # The tests' own database. The app never connects to it: the test
    # tooling (tests/_testdb.py) reads it, checks it ends in "_test" and is
    # not DATABASE_URL, and only then points DATABASE_URL at it.
    test_database_url: str | None = None

    # --- Sessions (D4) ---
    # RS256 key pair that signs the access tokens, relative to backend/
    # (scripts/generate_rsa_keypair.py writes it; keys/ is not in git).
    # Token lifetimes, password policy and login limits are business
    # parameters, not settings: app/services/parameters.py ("auth").
    jwt_private_key_path: str = "keys/jwt_private.pem"
    jwt_public_key_path: str = "keys/jwt_public.pem"
    # "iss" and "aud" of the access tokens. The day the corporate SSO
    # arrives they become the IdP's (app/core/security.py).
    jwt_issuer: str = "aal"
    jwt_audience: str = "aal-api"
    # Secure flag of the refresh cookie. Browsers accept Secure cookies on
    # http://localhost, so it stays on in development too; turn it off only
    # for a plain-HTTP host that is not localhost.
    refresh_cookie_secure: bool = True

    # --- CORS ---
    # The addresses the browser uses. Never "*" (refused below).
    cors_origins: list[str] = ["http://localhost:5173"]

    # --- AACF ---
    # The framework copy's VERSION file, answered by GET /api/version. A
    # relative path is taken from backend/.
    aacf_version_file: str = "../aacf/VERSION"

    @field_validator("cors_origins")
    @classmethod
    def _no_wildcard_origin(cls, origins: list[str]) -> list[str]:
        if any(origin.strip() == "*" for origin in origins):
            raise ValueError('CORS_ORIGINS must list the real origins, never "*"')
        return origins

    @field_validator("environment")
    @classmethod
    def _known_environment(cls, value: str) -> str:
        if value not in ("development", "production"):
            raise ValueError('ENVIRONMENT must be "development" or "production"')
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
