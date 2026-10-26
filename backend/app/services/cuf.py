"""The CUF and its normalized functional configuration (E11, NT §8).

A CUF includes subcategories of material; its normalized configuration is
the union, without duplicates, of the SNS those subcategories have in the
CUF's catalog version (NT §8.1.1), each SNS with the subcategories it comes
from. It is computed, never stored.

Two extension points for the encargos that follow:
- SUBCATEGORY_REMOVAL_GUARDS: before a subcategory leaves a CUF, each guard
  may answer why it cannot (from E13: its SNS are used by the CONFUNFIS).
- MATERIAL_COPIERS: "Crear CUF a partir de otro" runs every registered
  copier, in order; E12-E15 add the CONFUNFIS, the parts table and the
  functional products without touching the endpoint.
"""

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Material, MaterialSubcategoryLink, SubcategorySns, UserMaterialRole


async def subcategory_codes(db: AsyncSession, material_id: uuid.UUID) -> list[str]:
    rows = await db.execute(
        select(MaterialSubcategoryLink.subcategory_code).where(MaterialSubcategoryLink.material_id == material_id).order_by(MaterialSubcategoryLink.subcategory_code)
    )
    return list(rows.scalars())


async def sns_by_subcategory(db: AsyncSession, version_id: uuid.UUID, codes: list[str] | None = None) -> dict[str, set[str]]:
    """subcategory -> its SNS in `version_id` (all subcategories, or `codes`)."""
    query = select(SubcategorySns.subcategory_code, SubcategorySns.sns).where(
        SubcategorySns.version_id == version_id, SubcategorySns.subcategory_code.is_not(None)
    )
    if codes is not None:
        query = query.where(SubcategorySns.subcategory_code.in_(codes))
    out: dict[str, set[str]] = {}
    for sub, sns in await db.execute(query):
        out.setdefault(sub, set()).add(sns)
    return out


def union(by_sub: dict[str, set[str]]) -> dict[str, list[str]]:
    """sns -> the subcategories it comes from (sorted)."""
    out: dict[str, list[str]] = {}
    for sub in sorted(by_sub):
        for sns in by_sub[sub]:
            out.setdefault(sns, []).append(sub)
    return out


async def normalized_config(db: AsyncSession, material: Material) -> dict[str, list[str]]:
    """The CUF's normalized configuration: sns -> its subcategories of origin."""
    if material.catalog_version_id is None:
        return {}
    codes = await subcategory_codes(db, material.id)
    return union(await sns_by_subcategory(db, material.catalog_version_id, codes)) if codes else {}


# A guard answers why the subcategories `removed` cannot leave `material`
# (an error code and params), or None.
RemovalGuard = Callable[[AsyncSession, Material, set[str]], Awaitable[tuple[str, dict[str, Any]] | None]]
SUBCATEGORY_REMOVAL_GUARDS: list[RemovalGuard] = []


async def removal_problem(db: AsyncSession, material: Material, removed: set[str]) -> tuple[str, dict[str, Any]] | None:
    for guard in SUBCATEGORY_REMOVAL_GUARDS:
        problem = await guard(db, material, removed)
        if problem:
            return problem
    return None


async def set_subcategories(db: AsyncSession, material: Material, codes: set[str]) -> None:
    await db.execute(delete(MaterialSubcategoryLink).where(MaterialSubcategoryLink.material_id == material.id))
    for code in sorted(codes):
        db.add(MaterialSubcategoryLink(material_id=material.id, subcategory_code=code))
    await db.flush()


@dataclass(frozen=True)
class CopyOptions:
    copy_members: bool
    # Who copies (the copiers' audit and created_by, D11).
    user_id: uuid.UUID | None = None


# A copier copies one aspect of `source` into the new `target` (no commit).
Copier = Callable[[AsyncSession, Material, Material, CopyOptions], Awaitable[None]]
MATERIAL_COPIERS: list[tuple[str, Copier]] = []


def register_copier(name: str) -> Callable[[Copier], Copier]:
    def decorate(fn: Copier) -> Copier:
        MATERIAL_COPIERS.append((name, fn))
        return fn

    return decorate


@register_copier("subcategorias")
async def _copy_subcategories(db: AsyncSession, source: Material, target: Material, options: CopyOptions) -> None:
    await set_subcategories(db, target, set(await subcategory_codes(db, source.id)))


@register_copier("miembros")
async def _copy_members(db: AsyncSession, source: Material, target: Material, options: CopyOptions) -> None:
    if not options.copy_members:
        return
    members = (await db.execute(select(UserMaterialRole).where(UserMaterialRole.material_id == source.id))).scalars().all()
    for m in members:
        db.add(UserMaterialRole(user_id=m.user_id, material_id=target.id, role_code=m.role_code))
    await db.flush()


# What else changing the catalog version touches (E13: the CONFUNFIS rows
# whose SNS goes): each adds its keys to the impact report.
ImpactExtension = Callable[[AsyncSession, Material, dict[str, Any]], Awaitable[dict[str, Any]]]
IMPACT_EXTENSIONS: list[ImpactExtension] = []


async def impact(db: AsyncSession, material: Material, to_version_id: uuid.UUID) -> dict[str, Any]:
    """What changing the CUF to another catalog version does to its
    normalized configuration: SNS that appear and disappear, and the CUF's
    subcategories that the other version does not have (they would leave
    the CUF), and what IMPACT_EXTENSIONS add (E13: the CONFUNFIS rows)."""
    codes = await subcategory_codes(db, material.id)
    before = set(await normalized_config(db, material))
    target = await sns_by_subcategory(db, to_version_id, codes)
    after = set(union(target))
    report: dict[str, Any] = {
        "added": sorted(after - before),
        "removed": sorted(before - after),
        "subcategories_missing": sorted(set(codes) - set(target)),
        "sns_before": len(before),
        "sns_after": len(after),
    }
    for extension in IMPACT_EXTENSIONS:
        report.update(await extension(db, material, report))
    return report
