"""Passwords and tokens (D4). The ONLY place that signs or validates a JWT.

Access tokens are RS256 JWTs: signed with the private key, validated with
the public key, with "iss", "aud", "sub" (the user id), "iat" and "exp".
Validating with a public key is what a corporate IdP (SSO + MFA) also
needs: the day it arrives, only `_verification_keys()` changes -- it reads
the IdP's keys from its JWKS endpoint instead of keys/jwt_public.pem --
and JWT_ISSUER / JWT_AUDIENCE take the IdP's values. The authorization
(app/api/deps.py: who the user is, what they may do on each material)
does not change.

Refresh tokens are random strings, not JWTs: they are looked up (by their
SHA-256) and revoked in the database (app/services/sessions.py).
"""

import hashlib
import secrets
import string
import uuid
from datetime import UTC, datetime, timedelta
from functools import lru_cache

import bcrypt
import jwt

from app.core.config import backend_path, get_settings

JWT_ALGORITHM = "RS256"

# bcrypt's own limit (a fact of the algorithm, not a policy): it ignores
# what comes after 72 bytes, so a longer password is refused, never cut.
BCRYPT_MAX_PASSWORD_BYTES = 72

# Unambiguous characters for a temporary password an admin may read aloud
# (no 0/O, 1/l/I).
_TEMPORARY_ALPHABET = "".join(c for c in string.ascii_letters + string.digits if c not in "0O1lI") + "!@#$%&*+-?"


class PasswordTooLong(ValueError):
    """Over bcrypt's 72 bytes."""


def hash_password(password: str) -> str:
    encoded = password.encode("utf-8")
    if len(encoded) > BCRYPT_MAX_PASSWORD_BYTES:
        raise PasswordTooLong(f"a password has at most {BCRYPT_MAX_PASSWORD_BYTES} bytes")
    return bcrypt.hashpw(encoded, bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    encoded = password.encode("utf-8")
    if len(encoded) > BCRYPT_MAX_PASSWORD_BYTES:
        return False
    return bcrypt.checkpw(encoded, password_hash.encode("ascii"))


# A hash of a random password, checked when the email does not exist, so
# that an unknown email takes as long as a wrong password.
_DUMMY_HASH = bcrypt.hashpw(secrets.token_bytes(16).hex().encode("ascii"), bcrypt.gensalt()).decode("ascii")


def burn_password_check(password: str) -> None:
    verify_password(password, _DUMMY_HASH)


def generate_temporary_password(length: int) -> str:
    """A cryptographically random one-time password (`secrets`, never
    `random`). Returned once to the admin, never stored or logged."""
    return "".join(secrets.choice(_TEMPORARY_ALPHABET) for _ in range(length))


@lru_cache
def _signing_key() -> str:
    return backend_path(get_settings().jwt_private_key_path).read_text(encoding="utf-8")


@lru_cache
def _verification_keys() -> tuple[str, ...]:
    """The public keys an access token may be signed with. Today the local
    key pair's; with the corporate SSO, the IdP's (JWKS)."""
    return (backend_path(get_settings().jwt_public_key_path).read_text(encoding="utf-8"),)


def jwt_keys_missing() -> list[str]:
    """The key files that are not there (relative to backend/)."""
    settings = get_settings()
    return [p for p in (settings.jwt_private_key_path, settings.jwt_public_key_path) if not backend_path(p).is_file()]


def create_access_token(user_id: uuid.UUID, lifetime: timedelta) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "sub": str(user_id),
        "iat": now,
        "exp": now + lifetime,
    }
    return jwt.encode(payload, _signing_key(), algorithm=JWT_ALGORITHM)


class InvalidAccessToken(Exception):
    """Expired, signed with another key, for another audience, malformed...
    The caller never tells the client which."""


def access_token_subject(token: str) -> uuid.UUID:
    """The user id of a valid access token, or InvalidAccessToken."""
    settings = get_settings()
    for key in _verification_keys():
        try:
            payload = jwt.decode(
                token,
                key,
                algorithms=[JWT_ALGORITHM],
                audience=settings.jwt_audience,
                issuer=settings.jwt_issuer,
                options={"require": ["exp", "iat", "sub", "iss", "aud"]},
            )
        except jwt.InvalidSignatureError:
            continue
        except jwt.PyJWTError as exc:
            raise InvalidAccessToken(type(exc).__name__) from exc
        try:
            return uuid.UUID(str(payload["sub"]))
        except ValueError as exc:
            raise InvalidAccessToken("sub is not a user id") from exc
    raise InvalidAccessToken("signature")


def generate_refresh_token() -> tuple[str, str]:
    """(token, its SHA-256). The token goes to the cookie, only the hash to
    the database."""
    raw = secrets.token_urlsafe(48)
    return raw, hash_refresh_token(raw)


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
