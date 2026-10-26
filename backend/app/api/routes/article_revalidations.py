"""Revalidating every article (E13, app/services/revalidation.py): the
admin's button, and where the last run stands (any signed-in user: the
list's findings depend on it)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, require_admin
from app.core.errors import error_detail
from app.db.base import get_db
from app.models import ArticleRevalidation, User
from app.schemas.articles import RevalidationOut
from app.services import audit, revalidation
from app.services.snapshots import client_ip

router = APIRouter(prefix="/api/article-revalidations", tags=["articles"])


async def revalidation_out(db: AsyncSession, found: ArticleRevalidation) -> RevalidationOut:
    found = await revalidation.reap_if_stale(db, found)
    by = await db.scalar(select(User.display_name).where(User.id == found.created_by)) if found.created_by else None
    return RevalidationOut(
        id=found.id, reason=found.reason, detail=found.detail, status=found.status, report=found.report, error_code=found.error_code,
        created_by=by, created_at=found.created_at, finished_at=found.finished_at,
    )


@router.post("", response_model=RevalidationOut, status_code=status.HTTP_202_ACCEPTED)
async def start_revalidation(request: Request, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)) -> RevalidationOut:
    found = await revalidation.request(db, "manual", {}, admin.id)
    audit.record(db, action="articles.revalidation_requested", entity_type="article_revalidation", entity_id=str(found.id), user_id=admin.id, ip=client_ip(request))
    await db.commit()
    revalidation.schedule(found.id)
    return await revalidation_out(db, found)


@router.get("/latest", response_model=RevalidationOut | None)
async def latest_revalidation(_user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> RevalidationOut | None:
    found = (await db.execute(select(ArticleRevalidation).order_by(ArticleRevalidation.created_at.desc()).limit(1))).scalar_one_or_none()
    return await revalidation_out(db, found) if found else None


@router.get("/{run_id}", response_model=RevalidationOut)
async def get_revalidation(run_id: uuid.UUID, _user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> RevalidationOut:
    found = await db.get(ArticleRevalidation, run_id)
    if found is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_detail("revalidation_not_found"))
    return await revalidation_out(db, found)
