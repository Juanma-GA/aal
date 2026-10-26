"""The article master (E12): its data as PRISMA code -> value, the checks
that run on every save, "dónde se usa" and who may edit.

- `data_of(article)` / `set_data(article, data)`: the 26 field columns,
  the NOC (cdART) and the name (NomArt) by PRISMA code; the life controls
  apart (`life_of`, `set_life`).
- `recheck(db, article)`: AR-001…AR-007 over its data, kept on the article
  (findings, finding_codes) so the list filters by rule.
- References (E13, NT §9.1.6): `set_principal` writes the P/N + NCAGE that
  the Fichero Carga's world calls "the" article's (its principal
  reference); `reference_owner` says which article has a P/N + NCAGE.
- `USAGE_PROVIDERS` / `register_usage`: where an article is used. E12 has
  one provider ("Es el CUF del material X": a material with its NOC);
  E13/E14 add the CONFUNFIS positions, the parts and the functional
  products, E17 the "affects a CUF with a baseline" warning, without
  touching the endpoint.
- `can_edit_articles(db, user)`: the article is global, so the permission
  articulos.editar of any material the user is in (the matrix in BD, D5),
  or an admin.
"""

import re
from collections.abc import Awaitable, Callable
from decimal import Decimal
from typing import Any

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    FIELD_COLUMNS,
    MAX_LIFE_CONTROLS,
    Article,
    ArticleLifeControl,
    ArticleReference,
    Material,
    PhysicalPosition,
    RolePermission,
    User,
    UserMaterialRole,
)
from app.schemas.materials import NCAGE_PATTERN, NOC_PATTERN, normalize_code
from app.services.article_fields import FieldDef, field_defs
from app.services.reference import codes_by_state
from app.validacion.articulos import LifeControl, check

EDIT_PERMISSION = "articulos.editar"
IDENTITY = ("noc", "pn", "ncage", "nombre", "origen_nombre")
# The P/N of a reference (MAR06 has no field for it: E12's length).
PN_MAX_LENGTH = 32


def normalize_identity(noc: Any, pn: Any, ncage: Any) -> tuple[str | None, str | None, str | None, list[str]]:
    """NOC/NPC and NCAGE as E10/E11 check them (upper case, no spaces; the
    NPC's X in position 7 is a letter like any other), the P/N trimmed;
    with the names of the wrong ones."""
    noc, ncage = normalize_code(noc), normalize_code(ncage)
    pn = pn.strip() or None if isinstance(pn, str) else pn
    wrong = []
    if noc is not None and not re.fullmatch(NOC_PATTERN, str(noc)):
        wrong.append("noc")
    if ncage is not None and not re.fullmatch(NCAGE_PATTERN, str(ncage)):
        wrong.append("ncage")
    return noc, pn, ncage, wrong


def data_of(article: Article) -> dict[str, Any]:
    return {prisma: getattr(article, column) for prisma, column in FIELD_COLUMNS.items()}


def set_data(article: Article, data: dict[str, Any]) -> None:
    for prisma, column in FIELD_COLUMNS.items():
        if prisma in data:
            setattr(article, column, data[prisma])


def life_of(article: Article) -> list[LifeControl]:
    return [LifeControl(c.unit_code, c.quantity) for c in sorted(article.life_controls, key=lambda c: c.position)]


def _empty_pair(c: LifeControl) -> bool:
    return c.unit_code in (None, "") and c.quantity is None


def set_life(article: Article, life: list[LifeControl]) -> None:
    """Replaces the life controls, each at its position: only the empty
    pairs at the end are dropped, so an empty first pair (a Fichero Carga
    row without one) never moves the second into its place."""
    kept = list(life[:MAX_LIFE_CONTROLS])
    while kept and _empty_pair(kept[-1]):
        kept.pop()
    article.life_controls = [ArticleLifeControl(position=i, unit_code=c.unit_code or None, quantity=c.quantity) for i, c in enumerate(kept, start=1)]


def _plain(value: Any) -> Any:
    return str(value) if isinstance(value, Decimal) else value


def reference_snapshot(r: ArticleReference) -> dict[str, Any]:
    return {"id": str(r.id), "pn": r.pn, "ncage": r.ncage, "principal": r.principal, "origin": r.origin}


def snapshot(article: Article) -> dict[str, Any]:
    """The article as the audit keeps it."""
    return {
        **{k: getattr(article, k) for k in IDENTITY},
        "references": [reference_snapshot(r) for r in article.live_references],
        "fields": {prisma: _plain(v) for prisma, v in data_of(article).items() if prisma not in ("cdART", "NomArt")},
        "life_controls": [{"unit_code": c.unit_code, "quantity": _plain(c.quantity)} for c in life_of(article)],
    }


async def reference_owner(db: AsyncSession, pn: str, ncage: str | None, *, exclude: uuid.UUID | None = None) -> uuid.UUID | None:
    """The live article with this P/N + NCAGE (unique only with both)."""
    if not ncage:
        return None
    query = select(ArticleReference.article_id).join(Article, Article.id == ArticleReference.article_id).where(
        ArticleReference.pn == pn, ArticleReference.ncage == ncage, ArticleReference.deleted_at.is_(None), Article.deleted_at.is_(None)
    )
    if exclude is not None:
        query = query.where(ArticleReference.article_id != exclude)
    return (await db.execute(query.limit(1))).scalar_one_or_none()


async def _reference_in_use(db: AsyncSession, reference_id: uuid.UUID) -> bool:
    query = select(PhysicalPosition.id).where(PhysicalPosition.article_reference_id == reference_id, PhysicalPosition.deleted_at.is_(None))
    return (await db.execute(query.limit(1))).first() is not None


async def set_principal(db: AsyncSession, article: Article, pn: str | None, ncage: str | None, user_id: uuid.UUID | None, origin: str) -> None:
    """The article's principal P/N + NCAGE becomes this one:
    - a principal a CONFUNFIS row uses is never changed nor removed: it
      becomes another reference, and the new one the principal (E13);
    - both empty: the principal reference is removed (logically);
    - one of its other references: that one becomes the principal;
    - otherwise the principal changes in place (or is created).
    The caller has checked that no other article has it and that an NCAGE
    never comes without its P/N."""
    current = article.principal_reference
    if current is not None and (current.pn, current.ncage) == (pn, ncage):
        return
    # A principal a CONFUNFIS row is linked to keeps its P/N (that row's
    # component is still that one): it stays as another reference (E13).
    if current is not None and await _reference_in_use(db, current.id):
        current.principal, current.version, current.updated_by = False, current.version + 1, user_id
        await db.flush()
        current = None
    if pn is None:
        if current is not None:
            current.deleted_at, current.version, current.updated_by = datetime.now(UTC), current.version + 1, user_id
        return
    other = next((r for r in article.live_references if not r.principal and (r.pn, r.ncage) == (pn, ncage)), None)
    if other is not None:
        if current is not None:
            current.principal, current.version, current.updated_by = False, current.version + 1, user_id
            await db.flush()  # one live principal at a time (uq_article_reference_principal)
        other.principal, other.version, other.updated_by = True, other.version + 1, user_id
    elif current is not None:
        current.pn, current.ncage, current.version, current.updated_by = pn, ncage, current.version + 1, user_id
    else:
        article.references.append(
            ArticleReference(id=uuid.uuid4(), pn=pn, ncage=ncage, principal=True, origin=origin, version=1, created_by=user_id, updated_by=user_id)
        )


async def references_for(db: AsyncSession, defs: dict[str, FieldDef]) -> dict[str, dict[str, bool]]:
    tables = {d.table for d in defs.values() if d.table} | {"D114"}
    return {t: await codes_by_state(db, t) for t in sorted(tables)}


class Checker:
    """The definitions and reference codes, read once for many articles."""

    def __init__(self, defs: dict[str, FieldDef], references: dict[str, dict[str, bool]]):
        self.defs, self.references = defs, references

    @classmethod
    async def load(cls, db: AsyncSession) -> "Checker":
        defs = await field_defs(db)
        return cls(defs, await references_for(db, defs))

    def findings(self, data: dict[str, Any], life: list[LifeControl]) -> list[dict[str, Any]]:
        return check(data, life, self.defs, self.references)

    def recheck(self, article: Article) -> list[dict[str, Any]]:
        found = self.findings(data_of(article), life_of(article))
        article.findings = found
        article.finding_codes = sorted({f["code"] for f in found})
        return found


# (db, article, the user asking): only what that user may open (a material
# they are not in stays unknown to them, as a 404 does).
UsageProvider = Callable[[AsyncSession, Article, User], Awaitable[list[dict[str, Any]]]]
USAGE_PROVIDERS: list[tuple[str, UsageProvider]] = []


def register_usage(name: str) -> Callable[[UsageProvider], UsageProvider]:
    def decorate(fn: UsageProvider) -> UsageProvider:
        USAGE_PROVIDERS.append((name, fn))
        return fn

    return decorate


@register_usage("cuf")
async def _cuf_of_material(db: AsyncSession, article: Article, user: User) -> list[dict[str, Any]]:
    """The article is the CUF of a material: the material has its NOC."""
    if article.noc is None:
        return []
    query = select(Material.id, Material.name).where(Material.noc == article.noc, Material.deleted_at.is_(None))
    if not user.is_admin:
        query = query.join(UserMaterialRole, (UserMaterialRole.material_id == Material.id) & (UserMaterialRole.user_id == user.id))
    rows = (await db.execute(query.order_by(Material.name))).all()
    return [{"kind": "material_cuf", "material_id": str(mid), "material_name": name} for mid, name in rows]


async def where_used(db: AsyncSession, article: Article, user: User) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for _name, provider in USAGE_PROVIDERS:
        out += await provider(db, article, user)
    return out


async def can_edit_articles(db: AsyncSession, user: User) -> bool:
    if user.is_admin:
        return True
    found = await db.scalar(
        select(UserMaterialRole.material_id)
        .join(RolePermission, RolePermission.role_code == UserMaterialRole.role_code)
        .join(Material, Material.id == UserMaterialRole.material_id)
        .where(UserMaterialRole.user_id == user.id, RolePermission.permission_code == EDIT_PERMISSION, Material.deleted_at.is_(None))
        .limit(1)
    )
    return found is not None
