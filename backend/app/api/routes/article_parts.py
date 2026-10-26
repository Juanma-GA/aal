"""The parts table of an article (E14, NT §9.1.10): the breakdown of the
article itself, global like the master (D16), the same in every CUF that
mounts it. Reading is for any signed-in user; editing needs
articulos.editar in some material, as the article (E12). Each part goes
with its version and is audited on the article.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.api.routes.confunfis import alps_of, articles_by_id, part_out
from app.api.routes.users import confirmation_required, version_conflict
from app.core.errors import error_detail
from app.db.base import get_db
from app.models import Article, ArticlePart, ArticleReference, User
from app.schemas.confunfis import VersionIn
from app.schemas.confunfis_extras import PartIn, PartOut, PartUpdate
from app.services import confunfis_extras as extras
from app.services.articles import can_edit_articles
from app.services.parameters import get_parameter
from app.services.snapshots import client_ip

router = APIRouter(prefix="/api/articles/{article_id}/parts", tags=["articles"])

_IDENTITY = ("article_id", "noc", "pn", "ncage")


def _error(code: str, http: int = status.HTTP_409_CONFLICT) -> HTTPException:
    return HTTPException(status_code=http, detail=error_detail(code))


async def _parent(db: AsyncSession, article_id: uuid.UUID, *, lock: bool = False) -> Article:
    """The article; locked, one change of its breakdown at a time."""
    query = select(Article).where(Article.id == article_id, Article.deleted_at.is_(None))
    article = (await db.execute(query.with_for_update() if lock else query)).scalar_one_or_none()
    if article is None:
        raise _error("article_not_found", status.HTTP_404_NOT_FOUND)
    return article


async def _editor(db: AsyncSession, user: User) -> None:
    if not await can_edit_articles(db, user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_detail("permission_denied", permission="articulos.editar"))


async def _part(db: AsyncSession, parent: Article, part_id: uuid.UUID, version: int) -> ArticlePart:
    part = (
        await db.execute(
            select(ArticlePart).where(ArticlePart.id == part_id, ArticlePart.parent_article_id == parent.id, ArticlePart.deleted_at.is_(None)).with_for_update()
        )
    ).scalar_one_or_none()
    if part is None:
        raise _error("article_part_not_found", status.HTTP_404_NOT_FOUND)
    if part.version != version:
        raise version_conflict(part.version)
    return part


async def _identity_after(db: AsyncSession, part: ArticlePart, body: PartUpdate, sent: set[str]) -> dict:
    """What the part is linked by after an edit: the fields sent, the
    others as the part's article has them (sending a P/N alone keeps the NOC)."""
    if "article_id" in sent and body.article_id:
        return {"article_id": body.article_id}
    current = await db.get(Article, part.part_article_id) if part.part_article_id else None
    reference = next((r for r in current.live_references if r.id == part.article_reference_id), None) if current else None
    now = {"noc": current.noc if current else None, "pn": reference.pn if reference else None, "ncage": reference.ncage if reference else None}
    return {k: getattr(body, k) if k in sent else now[k] for k in ("noc", "pn", "ncage")}


def _invalid(exc: extras.ExtraError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=error_detail("article_part_invalid", problems=exc.problems))


async def _list(db: AsyncSession, parent_id: uuid.UUID) -> list[PartOut]:
    parts = await extras.live_parts(db, parent_id)
    articles = await articles_by_id(db, {p.part_article_id for p in parts})
    alps = alps_of(parts)
    return [part_out(p, articles, alps) for p in parts]


async def _done(db: AsyncSession, parent_id: uuid.UUID, part_id: uuid.UUID) -> PartOut:
    await extras.refresh_parts(db, {parent_id})
    await db.commit()
    return next(p for p in await _list(db, parent_id) if p.id == part_id)


@router.get("", response_model=list[PartOut])
async def list_parts(article_id: uuid.UUID, _user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> list[PartOut]:
    await _parent(db, article_id)
    return await _list(db, article_id)


@router.post("", response_model=PartOut, status_code=status.HTTP_201_CREATED)
async def create_part(article_id: uuid.UUID, body: PartIn, request: Request, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> PartOut:
    await _editor(db, user)
    parent = await _parent(db, article_id, lock=True)
    identity = {k: getattr(body, k) for k in _IDENTITY}
    try:
        part = await extras.save_part(db, parent, body.model_dump(exclude=set(_IDENTITY)), user.id, source="manual", strict=True, identity=identity, ip=client_ip(request))
    except extras.ExtraError as exc:
        raise _invalid(exc) from None
    except IntegrityError:
        raise _error("article_identity_taken") from None
    return await _done(db, parent.id, part.id)


@router.patch("/{part_id}", response_model=PartOut)
async def update_part(
    article_id: uuid.UUID, part_id: uuid.UUID, body: PartUpdate, request: Request, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
) -> PartOut:
    await _editor(db, user)
    parent = await _parent(db, article_id, lock=True)
    part = await _part(db, parent, part_id, body.version)
    sent = body.model_fields_set - {"version"}
    values = {**extras.snapshot(part, extras.PART_FIELDS), **{k: getattr(body, k) for k in sent if k in extras.PART_FIELDS}}
    checked = {k for k in sent if k in extras.PART_FIELDS and getattr(body, k) != getattr(part, k)}
    identity = await _identity_after(db, part, body, sent) if sent & set(_IDENTITY) else None
    try:
        await extras.save_part(db, parent, values, user.id, source=part.source, strict=True, part=part, identity=identity, checked=checked, ip=client_ip(request))
    except extras.ExtraError as exc:
        raise _invalid(exc) from None
    except IntegrityError:
        raise _error("article_identity_taken") from None
    return await _done(db, parent.id, part.id)


@router.delete("/{part_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_part(
    article_id: uuid.UUID, part_id: uuid.UUID, version: int, request: Request, confirm: bool = False, reset_alp: bool = False,
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
) -> None:
    """Removed logically (HR9). `reset_alp`: an ALP left alone in its COP
    goes back to 00, as the AL of a CONFUNFIS row (E14)."""
    await _editor(db, user)
    if not confirm:
        raise confirmation_required()
    parent = await _parent(db, article_id, lock=True)
    part = await _part(db, parent, part_id, version)
    ip = client_ip(request)
    await extras.remove_part(db, part, user.id, ip)
    if reset_alp:
        await extras.reset_alone_alp(db, parent, part.cop, user.id, ip)
    await extras.refresh_parts(db, {parent.id})
    await db.commit()


@router.post("/{part_id}/reset-alp", response_model=PartOut)
async def reset_alp(
    article_id: uuid.UUID, part_id: uuid.UUID, body: VersionIn, request: Request, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
) -> PartOut:
    """"Volver a ALP 00": an ALP alone in its COP (OP-006)."""
    await _editor(db, user)
    parent = await _parent(db, article_id, lock=True)
    part = await _part(db, parent, part_id, body.version)
    if not await extras.reset_alone_alp(db, parent, part.cop, user.id, client_ip(request)):
        raise _error("article_part_not_single_alternative")
    return await _done(db, parent.id, part.id)


@router.post("/{part_id}/duplicate-alternative", response_model=PartOut, status_code=status.HTTP_201_CREATED)
async def duplicate_alternative(
    article_id: uuid.UUID, part_id: uuid.UUID, body: VersionIn, request: Request, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
) -> PartOut:
    """Same COP and quantity, the next free ALP; a part without
    alternatives (ALP 00) becomes 01 first and the copy takes 02."""
    await _editor(db, user)
    parent = await _parent(db, article_id, lock=True)
    part = await _part(db, parent, part_id, body.version)
    bounds = (await get_parameter(db, "confunfis"))["alp"]
    ip = client_ip(request)
    same = [p for p in await extras.live_parts(db, parent.id) if p.cop == part.cop]
    used = {int(p.alp) for p in same if p.alp.isdigit()}
    free = [n for n in range(max(1, bounds["min"]), bounds["max"] + 1) if n not in used]
    if len(free) < (2 if part.alp == "00" else 1):
        raise _error("article_part_no_free_alternative")
    if part.alp == "00":
        for p in [p for p in same if p.alp == "00"]:
            await extras.save_part(db, parent, {**extras.snapshot(p, extras.PART_FIELDS), "alp": f"{free[0]:02d}"}, user.id, source=p.source, strict=False, part=p, ip=ip)
        free.pop(0)
    # The same article and P/N + NCAGE as the original (in the copy's audit too).
    reference = await db.get(ArticleReference, part.article_reference_id) if part.article_reference_id else None
    identity = {"article_id": part.part_article_id, "pn": reference.pn if reference else None, "ncage": reference.ncage if reference else None}
    copy = await extras.save_part(
        db, parent, {**extras.snapshot(part, extras.PART_FIELDS), "alp": f"{free[0]:02d}"}, user.id, source="manual", strict=False,
        identity=identity if part.part_article_id else None, ip=ip,
    )
    return await _done(db, parent.id, copy.id)
