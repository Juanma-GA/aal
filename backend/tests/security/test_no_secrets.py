"""No password, password hash or token ever lands in audit_log or in the
server log, across every flow that handles one."""

import json
import logging

from sqlalchemy import select

from app.db.base import async_session_factory
from app.models import AuditLog, RefreshToken, User
from helpers import TEST_PASSWORD, bearer, login


async def test_no_secret_in_audit_log_or_logs(client, factory, caplog):
    caplog.set_level(logging.DEBUG)
    admin = await factory.user(is_admin=True)
    material = await factory.material()
    secrets: set[str] = {TEST_PASSWORD}

    admin_token, res = await login(client, admin)
    secrets |= {admin_token, res.cookies["aal_refresh"]}
    h = bearer(admin_token)

    created = (await client.post("/api/users", json={"email": "secreto@aal-test.es", "display_name": "Secreto"}, headers=h)).json()
    factory.user_ids.append(__import__("uuid").UUID(created["user"]["id"]))
    temporary = created["temporary_password"]
    secrets.add(temporary)
    reset = (await client.post(f"/api/users/{created['user']['id']}/reset-password", headers=h)).json()
    secrets.add(reset["temporary_password"])
    await client.put(f"/api/materials/{material.id}/members/{created['user']['id']}", json={"role": "analista"}, headers=h)

    client.cookies.clear()
    user_token, res = await login(client, "secreto@aal-test.es", reset["temporary_password"])
    secrets |= {user_token, res.cookies["aal_refresh"]}
    new_password = "Mi-contraseña-nueva-del-test-7"
    secrets.add(new_password)
    await client.post(
        "/api/me/password", json={"current_password": reset["temporary_password"], "new_password": new_password}, headers=bearer(user_token)
    )
    refreshed = await client.post("/api/auth/refresh")
    secrets |= {refreshed.json()["access_token"], refreshed.cookies["aal_refresh"]}
    await client.post("/api/auth/logout")
    await client.post("/api/auth/login", json={"email": "secreto@aal-test.es", "password": "contraseña-equivocada"})
    secrets.add("contraseña-equivocada")

    async with async_session_factory() as session:
        hashes = set((await session.execute(select(User.password_hash).where(User.id.in_(factory.user_ids)))).scalars().all())
        token_hashes = set((await session.execute(select(RefreshToken.token_hash))).scalars().all())
        rows = (await session.execute(select(AuditLog))).scalars().all()
    secrets |= hashes | token_hashes
    audit_text = json.dumps([{"before": r.before, "after": r.after, "entity_id": r.entity_id, "action": r.action} for r in rows], ensure_ascii=False)
    assert rows
    for name in ("password", "password_hash", "token", "access_token"):
        assert f'"{name}"' not in audit_text, name
    log_text = "\n".join(r.getMessage() + " " + json.dumps({k: str(v) for k, v in vars(r).items()}, ensure_ascii=False) for r in caplog.records)
    for secret in secrets:
        assert secret not in audit_text, "a secret in audit_log"
        assert secret not in log_text, "a secret in the logs"
