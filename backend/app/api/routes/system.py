from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.migrations import migration_status
from app.db.base import get_db
from app.schemas.system import HealthResponse, VersionResponse
from app.version import aacf_version, app_version

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health", response_model=HealthResponse)
async def health(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    """The app and its database: reachable and on which migration. A
    database that cannot be reached is a sanitized 503
    (database_unavailable, app/core/errors.py)."""
    await db.execute(text("SELECT 1"))
    migrations = await migration_status(await db.connection())
    return HealthResponse(status="ok", database={"status": "ok", "migrations": migrations})


@router.get("/version", response_model=VersionResponse)
async def version() -> VersionResponse:
    """The app's version and the AACF copy's."""
    return VersionResponse(app=app_version(), aacf=aacf_version())
