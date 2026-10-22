"""Creates the first global admin (there is no public registration):

    python scripts/create_admin_user.py admin@empresa.es      (from backend/)

The email comes as the argument or from INITIAL_ADMIN_EMAIL; the password
from INITIAL_ADMIN_PASSWORD or asked with getpass -- never as an argument
(D17). In PowerShell, to set it for one run without it ending in the
history: $env:INITIAL_ADMIN_PASSWORD = Read-Host -MaskInput (or let the
script ask). An existing email is never modified.
"""

import argparse
import asyncio
import os
import sys

from _common import secret, utf8_output

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import select

from app.core.security import BCRYPT_MAX_PASSWORD_BYTES, hash_password
from app.db.base import async_session_factory, engine
from app.models import User
from app.services import audit
from app.services.parameters import get_parameter


async def create(email: str, display_name: str) -> int:
    async with async_session_factory() as db:
        if (await db.execute(select(User).where(User.email == email))).scalar_one_or_none() is not None:
            print(f"Ya existe un usuario {email}: no se modifica.", file=sys.stderr)
            return 1
        policy = (await get_parameter(db, "auth"))["password"]
        password = secret("INITIAL_ADMIN_PASSWORD", "Contraseña del administrador")
        if len(password) < policy["min_length"] or len(password.encode("utf-8")) > BCRYPT_MAX_PASSWORD_BYTES:
            print(
                f"La contraseña debe tener al menos {policy['min_length']} caracteres y como mucho {BCRYPT_MAX_PASSWORD_BYTES} bytes.",
                file=sys.stderr,
            )
            return 1
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
    await engine.dispose()
    return 0


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
    return asyncio.run(create(email, args.name))


if __name__ == "__main__":
    utf8_output()
    sys.exit(main())
