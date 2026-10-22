"""The access token: RS256 signature, expiry, issuer and audience. Every
invalid token is the same 401."""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.config import backend_path, get_settings
from app.core.security import create_access_token
from helpers import bearer


def _private_key() -> str:
    return backend_path(get_settings().jwt_private_key_path).read_text(encoding="utf-8")


def _token(user_id, *, key=None, minutes=5, **overrides) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {"iss": settings.jwt_issuer, "aud": settings.jwt_audience, "sub": str(user_id), "iat": now, "exp": now + timedelta(minutes=minutes)}
    payload.update(overrides)
    payload = {k: v for k, v in payload.items() if v is not None}
    return jwt.encode(payload, key or _private_key(), algorithm="RS256")


async def _me(client, token):
    return await client.get("/api/auth/me", headers=bearer(token))


async def test_a_valid_token_is_accepted(client, factory):
    user = await factory.user()
    assert (await _me(client, create_access_token(user.id, timedelta(minutes=5)))).status_code == 200


async def test_rejected_tokens_all_answer_the_same_401(client, factory):
    user = await factory.user()
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    good = _token(user.id)
    tampered = good[:-4] + ("AAAA" if not good.endswith("AAAA") else "BBBB")
    none_alg = jwt.encode({"sub": str(user.id), "exp": datetime.now(UTC) + timedelta(minutes=5)}, key=None, algorithm="none")
    hs256 = jwt.encode(
        {"iss": "aal", "aud": "aal-api", "sub": str(user.id), "iat": datetime.now(UTC), "exp": datetime.now(UTC) + timedelta(minutes=5)},
        "clave-compartida-cualquiera-de-32-bytes!!",
        algorithm="HS256",
    )
    cases = {
        "expired": _token(user.id, minutes=-1),
        "signed with another key": _token(user.id, key=other_key),
        "tampered": tampered,
        "other audience": _token(user.id, aud="otra-api"),
        "other issuer": _token(user.id, iss="otro"),
        "no exp": _token(user.id, exp=None),
        "sub not a user id": _token(user.id, sub="admin"),
        "unknown user": _token(uuid.uuid4()),
        "alg none": none_alg,
        "HS256": hs256,
        "garbage": "no-es-un-jwt",
    }
    for name, token in cases.items():
        res = await _me(client, token)
        assert res.status_code == 401, name
        assert res.json() == {"detail": {"code": "not_authenticated"}}, name
        assert res.headers["WWW-Authenticate"] == "Bearer", name


async def test_no_token_is_401(client):
    res = await client.get("/api/auth/me")
    assert res.status_code == 401
