"""Development data: one synthetic material and three users, one per role
(analista, revisor, observador), assigned to it. Never on a server
(refused with ENVIRONMENT=production).

    python scripts/seed_dev_data.py        (from backend/)

The three passwords come from DEV_ANALISTA_PASSWORD, DEV_REVISOR_PASSWORD
and DEV_OBSERVADOR_PASSWORD, or are asked with getpass -- never arguments
(D17); each is checked as soon as it is typed and asked again when it breaks
the policy, and Ctrl+C cancels before anything is written
(scripts/_common.py). Running it again changes nothing that already exists
(it only adds what is missing).
"""

import asyncio
import sys

from _common import cancellable, new_password, utf8_output

from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.base import async_session_factory, engine
from app.models import Material, User, UserMaterialRole
from app.services import audit
from app.services.parameters import get_parameter

DEV_MATERIAL_NAME = "Material de desarrollo (sintético)"
DEV_USERS = (
    ("analista", "analista.dev@aal-dev.es", "Analista de desarrollo"),
    ("revisor", "revisor.dev@aal-dev.es", "Revisor de desarrollo"),
    ("observador", "observador.dev@aal-dev.es", "Observador de desarrollo"),
)


async def _missing_users() -> tuple[list[str], int]:
    """The emails of DEV_USERS still to create, and the policy's minimum
    password length."""
    try:
        async with async_session_factory() as db:
            emails = [email for _role, email, _name in DEV_USERS]
            existing = set((await db.execute(select(User.email).where(User.email.in_(emails)))).scalars())
            min_length = (await get_parameter(db, "auth"))["password"]["min_length"]
            return [email for email in emails if email not in existing], min_length
    finally:
        await engine.dispose()


async def seed(passwords: dict[str, str]) -> None:
    async with async_session_factory() as db:
        material = (
            await db.execute(select(Material).where(Material.name == DEV_MATERIAL_NAME, Material.deleted_at.is_(None)))
        ).scalar_one_or_none()
        if material is None:
            material = Material(name=DEV_MATERIAL_NAME, description="Datos sintéticos para desarrollo y pruebas.", version=1)
            db.add(material)
            await db.flush()
            audit.record(db, action="material.created", entity_type="material", entity_id=str(material.id), material_id=material.id, after={"name": material.name})
            print(f"Material creado: {material.name}")
        for role, email, name in DEV_USERS:
            user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if user is None:
                user = User(
                    email=email,
                    display_name=name,
                    password_hash=hash_password(passwords[email]),
                    is_admin=False,
                    is_active=True,
                    must_change_password=False,
                    ui_preferences={"active_material_id": str(material.id)},
                    version=1,
                )
                db.add(user)
                await db.flush()
                audit.record(db, action="user.created", entity_type="user", entity_id=str(user.id), after={"email": email})
                print(f"Usuario creado: {email}")
            assigned = await db.get(UserMaterialRole, (user.id, material.id))
            if assigned is None:
                db.add(UserMaterialRole(user_id=user.id, material_id=material.id, role_code=role))
                audit.record(
                    db,
                    action="material_role.assigned",
                    entity_type="user_material_role",
                    entity_id=f"{user.id}:{material.id}",
                    material_id=material.id,
                    after={"user": email, "role": role},
                )
                print(f"  {email}: {role} en {material.name}")
        await db.commit()
    await engine.dispose()


def main() -> int:
    if get_settings().environment == "production":
        print("seed_dev_data no se ejecuta con ENVIRONMENT=production.", file=sys.stderr)
        return 1
    missing, min_length = asyncio.run(_missing_users())
    # Asked before anything is written: Ctrl+C here leaves the base as it was.
    roles = {email: role for role, email, _name in DEV_USERS}
    passwords = {email: new_password(f"DEV_{roles[email].upper()}_PASSWORD", f"Contraseña de {email}", min_length) for email in missing}
    asyncio.run(seed(passwords))
    return 0


if __name__ == "__main__":
    utf8_output()
    sys.exit(cancellable(main))
