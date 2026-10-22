"""Removes what a browser check (scripts/verify-*.mjs) created, so the
database stays as it was. Only users of the verify domain
(@verify.aal-dev.es) and materials whose name starts with "[verify] "; never
on a server (ENVIRONMENT=production).

    python scripts/purge_verify_data.py --users nombre@verify.aal-dev.es
    python scripts/purge_verify_data.py --materials "[verify] Material ajeno"
                                                              (from backend/)

They are deleted for good, with their roles, sessions and failed logins.
Their audit_log rows stay: the log is append-only, and that run did happen.
"""

import argparse
import asyncio
import sys

from _common import utf8_output

from sqlalchemy import delete, select

from app.core.config import get_settings
from app.db.base import async_session_factory, engine
from app.models import LoginFailure, Material, User

VERIFY_DOMAIN = "@verify.aal-dev.es"
VERIFY_MATERIAL_PREFIX = "[verify] "


async def purge(emails: list[str], materials: list[str]) -> int:
    async with async_session_factory() as db:
        for email in emails:
            user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            await db.execute(delete(LoginFailure).where(LoginFailure.email == email))
            if user is not None:
                await db.delete(user)
                print(f"Usuario eliminado: {email}")
        for name in materials:
            for material in (await db.execute(select(Material).where(Material.name == name))).scalars().all():
                await db.delete(material)
                print(f"Material eliminado: {name}")
        await db.commit()
    await engine.dispose()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Elimina lo que han creado los verify-*.")
    parser.add_argument("--users", nargs="*", default=[], help=f"emails {VERIFY_DOMAIN}")
    parser.add_argument("--materials", nargs="*", default=[], help=f'nombres que empiezan por "{VERIFY_MATERIAL_PREFIX}"')
    args = parser.parse_args()
    if get_settings().environment == "production":
        print("No se ejecuta con ENVIRONMENT=production.", file=sys.stderr)
        return 1
    emails = [e.strip().lower() for e in args.users]
    wrong = [e for e in emails if not e.endswith(VERIFY_DOMAIN)] + [m for m in args.materials if not m.startswith(VERIFY_MATERIAL_PREFIX)]
    if wrong:
        print(f"Solo usuarios {VERIFY_DOMAIN} y materiales \"{VERIFY_MATERIAL_PREFIX}…\": {', '.join(wrong)}", file=sys.stderr)
        return 1
    return asyncio.run(purge(emails, args.materials))


if __name__ == "__main__":
    utf8_output()
    sys.exit(main())
