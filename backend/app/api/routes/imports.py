"""An Excel import job (E03), whatever its target: its state and report
(polled while the analysis runs) and phase 2, applying it."""

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.db.base import get_db
from app.models import ImportJob, User
from app.schemas.reference import ImportJobOut
from app.services import import_jobs
from app.services.snapshots import client_ip

router = APIRouter(prefix="/api/import-jobs", tags=["imports"])


def job_out(job: ImportJob) -> ImportJobOut:
    report = job.report or {}
    return ImportJobOut(
        id=job.id,
        template=job.template,
        params=job.params,
        status=job.status,
        file_name=job.file_name,
        counts=job.counts,
        report=report if job.status in ("analyzed", "applied") else None,
        error_code=job.error_code,
        error_params=report.get("error_params", {}) if job.status == "failed" else {},
        created_at=job.created_at,
        analyzed_at=job.analyzed_at,
        applied_at=job.applied_at,
    )


@router.get("/{job_id}", response_model=ImportJobOut)
async def get_import_job(job_id: uuid.UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> ImportJobOut:
    job = await import_jobs.reap_if_stale(db, await import_jobs.get_job(db, job_id, user))
    return job_out(job)


@router.post("/{job_id}/apply", response_model=ImportJobOut)
async def apply_import_job(
    job_id: uuid.UUID, request: Request, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
) -> ImportJobOut:
    return job_out(await import_jobs.apply(db, job_id, user, client_ip(request)))
