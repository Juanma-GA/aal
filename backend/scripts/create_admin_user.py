"""Creates the first global admin (there is no public registration):

    python scripts/create_admin_user.py admin@empresa.es      (from backend/)

The email comes as the argument or from INITIAL_ADMIN_EMAIL; the password
from INITIAL_ADMIN_PASSWORD or asked with getpass -- never as an argument
(D17). In PowerShell, to set it for one run without it ending in the
history: $env:INITIAL_ADMIN_PASSWORD = Read-Host -MaskInput (or let the
script ask). The password is checked as soon as it is typed and asked again
when it breaks the policy; Ctrl+C cancels (scripts/_common.py). An existing
email is never modified.
"""

import argparse
import asyncio
import os
import sys

from _common import cancellable, new_password, utf8_output

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import select

from app.core.security import hash_password
from app.db.base import async_session_factory, engine
from app.models import User
from app.services import audit
from app.services.parameters import get_parameter


async def _min_length(email: str) -> int | None:
    """The policy's minimum length, or None when the email already exists."""
    try:
        async with async_session_factory() as db:
            if (await db.execute(select(User).where(User.email == email))).scalar_one_or_none() is not None:
                return None
            return (await get_parameter(db, "auth"))["password"]["min_length"]
    finally:
        await engine.dispose()


async def _create(email: str, display_name: str, password: str) -> None:
    try:
        async with async_session_factory() as db:
            user = User(
                email=email,
                display_name=display_name,
                password_hash=hash_password(password),
                is_admin=True,
                is_active=True,
                must_change_password=False,
                ui_preferences={},
                version=1,
            )
            db.add(user)
            await db.flush()
            audit.record(db, action="user.created", entity_type="user", entity_id=str(user.id), after={"email": email, "is_admin": True})
            await db.commit()
            print(f"Administrador creado: {email} ({user.id}).")
    finally:
        await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description="Crea el primer administrador global.")
    parser.add_argument("email", nargs="?", help="email del administrador (o INITIAL_ADMIN_EMAIL)")
    parser.add_argument("--name", default="Administrador", help="nombre visible")
    args = parser.parse_args()
    raw = args.email or os.environ.get("INITIAL_ADMIN_EMAIL") or ""
    if not raw:
        print("Falta el email: como argumento o en INITIAL_ADMIN_EMAIL.", file=sys.stderr)
        return 1
    try:
        email = validate_email(raw, check_deliverability=False).normalized.lower()
    except EmailNotValidError as exc:
        print(f"Email no válido: {exc}", file=sys.stderr)
        return 1
    min_length = asyncio.run(_min_length(email))
    if min_length is None:
        print(f"Ya existe un usuario {email}: no se modifica.", file=sys.stderr)
        return 1
    password = new_password("INITIAL_ADMIN_PASSWORD", "Contraseña del administrador", min_length)
    asyncio.run(_create(email, args.name, password))
    return 0


if __name__ == "__main__":
    utf8_output()
    sys.exit(cancellable(main))
