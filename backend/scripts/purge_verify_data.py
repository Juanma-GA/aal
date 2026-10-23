"""Removes what a browser check (scripts/verify-*.mjs) created, so the
database stays as it was. Only users of the verify domain
(@verify.aal-dev.es) and materials whose name starts with "[verify] "; never
on a server (ENVIRONMENT=production).

    python scripts/purge_verify_data.py --users nombre@verify.aal-dev.es
    python scripts/purge_verify_data.py --materials "[verify] Material ajeno"
                                                              (from backend/)

They are deleted for good, with their roles, sessions and failed logins.
Their audit_log rows stay: the log is append-only, and that run did happen.

Reference tables a check edits (E03) are saved before and put back after,
every column of their values (version included) and the table's version;
a value the check added is removed. The import jobs it ran are removed.

    python scripts/purge_verify_data.py --save-reference D112 --snapshot FICHERO
    python scripts/purge_verify_data.py --restore-reference --snapshot FICHERO
    python scripts/purge_verify_data.py --import-jobs <id>

A catalog version a check imported (E10; only one whose file name starts
with "verify-") is removed with its SNS; the newest version left becomes
the active one again, categories and subcategories no version uses any more
are removed, and the names of the others come back from that version (an
import may have renamed them).

    python scripts/purge_verify_data.py --catalog-versions <id>

The requests for a new SNS a check created (E11) are removed for good.

    python scripts/purge_verify_data.py --sns-requests <id>
"""

import argparse
import asyncio
import json
import sys
import uuid
from pathlib import Path

from _common import utf8_output

from sqlalchemy import delete, select, update

from app.core.config import get_settings
from app.db.base import async_session_factory, engine
from app.models import (
    CatalogVersion,
    ImportJob,
    LoginFailure,
    Material,
    MaterialCategory,
    MaterialSubcategory,
    MaterialSubcategoryLink,
    ReferenceTable,
    ReferenceValue,
    SnsRequest,
    SubcategorySns,
    User,
)

_VALUE_COLUMNS = ("description", "definition", "attributes", "is_active", "sort_order", "version")

VERIFY_DOMAIN = "@verify.aal-dev.es"
VERIFY_MATERIAL_PREFIX = "[verify] "
VERIFY_FILE_PREFIX = "verify-"


async def save_reference(tables: list[str], snapshot: Path) -> int:
    async with async_session_factory() as db:
        saved = {}
        for code in tables:
            table = await db.get(ReferenceTable, code)
            if table is None:
                print(f"No existe la tabla {code}.", file=sys.stderr)
                return 1
            values = (await db.execute(select(ReferenceValue).where(ReferenceValue.table_code == code))).scalars()
            saved[code] = {"version": table.version, "values": {str(v.id): {c: getattr(v, c) for c in _VALUE_COLUMNS} for v in values}}
    await engine.dispose()
    snapshot.write_text(json.dumps(saved, ensure_ascii=False), encoding="utf-8")
    print(f"Tablas guardadas: {', '.join(tables)}")
    return 0


async def restore_reference(snapshot: Path) -> int:
    saved = json.loads(snapshot.read_text(encoding="utf-8"))
    async with async_session_factory() as db:
        for code, table in saved.items():
            ids = [uuid.UUID(i) for i in table["values"]]
            await db.execute(delete(ReferenceValue).where(ReferenceValue.table_code == code, ReferenceValue.id.not_in(ids)))
            for value_id, columns in table["values"].items():
                await db.execute(update(ReferenceValue).where(ReferenceValue.id == uuid.UUID(value_id)).values(**columns))
            await db.execute(update(ReferenceTable).where(ReferenceTable.code == code).values(version=table["version"]))
            print(f"Tabla restaurada: {code}")
        await db.commit()
    await engine.dispose()
    snapshot.unlink()
    return 0


async def purge_catalog_versions(db, versions: list[uuid.UUID]) -> int:
    marked = CatalogVersion.file_name.startswith(VERIFY_FILE_PREFIX)
    others = (await db.execute(select(CatalogVersion.number).where(CatalogVersion.id.in_(versions), ~marked))).scalars().all()
    if others:
        print(f'Solo versiones importadas por un verify (fichero "{VERIFY_FILE_PREFIX}…"); no: {others}', file=sys.stderr)
        return 1
    deleted = await db.execute(delete(CatalogVersion).where(CatalogVersion.id.in_(versions), marked))
    print(f"Versiones del catálogo eliminadas: {deleted.rowcount}")
    await db.flush()
    newest = (await db.execute(select(CatalogVersion).order_by(CatalogVersion.number.desc()).limit(1))).scalar_one_or_none()
    if newest is not None and (await db.execute(select(CatalogVersion).where(CatalogVersion.is_active))).scalar_one_or_none() is None:
        newest.is_active = True
        print(f"Versión activa de nuevo: {newest.number}")
    used = select(SubcategorySns.subcategory_code).where(SubcategorySns.subcategory_code.is_not(None))
    linked = select(MaterialSubcategoryLink.subcategory_code)
    await db.execute(delete(MaterialSubcategory).where(MaterialSubcategory.code.not_in(used), MaterialSubcategory.code.not_in(linked)))
    await db.execute(delete(MaterialCategory).where(MaterialCategory.code.not_in(select(MaterialSubcategory.category_code))))
    if newest is not None:
        rows = (
            await db.execute(
                select(SubcategorySns.subcategory_code, SubcategorySns.category_code, SubcategorySns.category_name, SubcategorySns.subcategory_name)
                .where(SubcategorySns.version_id == newest.id, SubcategorySns.subcategory_code.is_not(None))
                .order_by(SubcategorySns.row_number)
            )
        ).all()
        for code, name in {r.category_code: r.category_name for r in reversed(rows)}.items():
            await db.execute(update(MaterialCategory).where(MaterialCategory.code == code).values(name=name))
        for code, name in {r.subcategory_code: r.subcategory_name for r in reversed(rows)}.items():
            await db.execute(update(MaterialSubcategory).where(MaterialSubcategory.code == code).values(name=name))
    return 0


async def purge(emails: list[str], materials: list[str], jobs: list[uuid.UUID], versions: list[uuid.UUID], requests: list[uuid.UUID]) -> int:
    async with async_session_factory() as db:
        if requests:
            deleted = await db.execute(delete(SnsRequest).where(SnsRequest.id.in_(requests)))
            print(f"Solicitudes de SNS eliminadas: {deleted.rowcount}")
        if versions and await purge_catalog_versions(db, versions):
            return 1
        if jobs:
            await db.execute(delete(ImportJob).where(ImportJob.id.in_(jobs)))
            print(f"Importaciones eliminadas: {len(jobs)}")
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
    parser.add_argument("--import-jobs", nargs="*", default=[], type=uuid.UUID, help="ids de importaciones")
    parser.add_argument("--catalog-versions", nargs="*", default=[], type=uuid.UUID, help="ids de versiones del catálogo")
    parser.add_argument("--sns-requests", nargs="*", default=[], type=uuid.UUID, help="ids de solicitudes de SNS")
    parser.add_argument("--save-reference", nargs="*", default=[], help="tablas de referencia que guardar")
    parser.add_argument("--restore-reference", action="store_true", help="devuelve las tablas guardadas")
    parser.add_argument("--snapshot", type=Path, help="fichero de --save-reference / --restore-reference")
    args = parser.parse_args()
    if get_settings().environment == "production":
        print("No se ejecuta con ENVIRONMENT=production.", file=sys.stderr)
        return 1
    emails = [e.strip().lower() for e in args.users]
    wrong = [e for e in emails if not e.endswith(VERIFY_DOMAIN)] + [m for m in args.materials if not m.startswith(VERIFY_MATERIAL_PREFIX)]
    if wrong:
        print(f"Solo usuarios {VERIFY_DOMAIN} y materiales \"{VERIFY_MATERIAL_PREFIX}…\": {', '.join(wrong)}", file=sys.stderr)
        return 1
    if (args.save_reference or args.restore_reference) and not args.snapshot:
        print("--save-reference y --restore-reference necesitan --snapshot.", file=sys.stderr)
        return 1
    if args.save_reference:
        return asyncio.run(save_reference(args.save_reference, args.snapshot))
    if args.restore_reference:
        return asyncio.run(restore_reference(args.snapshot))
    return asyncio.run(purge(emails, args.materials, args.import_jobs, args.catalog_versions, args.sns_requests))


if __name__ == "__main__":
    utf8_output()
    sys.exit(main())
