"""The two phases of an Excel import (E03), for any target of app/io_excel.

1. start() checks the upload (reader.check_upload: .xlsx only, sizes),
   saves it under IMPORT_STAGING_DIR with a generated name and creates the
   import_job ("analyzing"); run_analysis() then runs in the background
   (FastAPI BackgroundTasks, its own session: the request's is closed by
   then) and leaves the report in the job ("analyzed") or the reason it
   failed ("failed"). The staged file is removed when the analysis ends.
   Nothing is written to the target's tables.
2. apply() writes that very analysis, in one transaction with an audit row
   per record, and only when it has no errors (409 import_has_errors). A
   record changed since the analysis stops it (409 import_stale): analyse
   again.

The frontend polls GET /api/import-jobs/{id}; Postgres is the only record
of where a job stands (HR1). An analysis whose process died stays
"analyzing" until someone reads it after `import.stale_minutes`, which
marks it failed (reap_if_stale).
"""

import asyncio
import hashlib
import logging
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePath
from typing import Any

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import backend_path, get_settings
from app.core.errors import error_detail, new_error_ref
from app.db.base import async_session_factory
from app.io_excel.analysis import analyze
from app.io_excel.reader import ExcelFileError, Limits, check_upload, read_rows
from app.io_excel.targets import ImportTarget, get_target
from app.models import ImportJob, User
from app.services import audit
from app.services.parameters import get_parameter
from app.services.reference import codes_by_state

logger = logging.getLogger("app.import_jobs")
_MB = 1024 * 1024
_FILE_NAME_MAX = 255


async def limits(db: AsyncSession) -> Limits:
    p = await get_parameter(db, "import")
    return Limits(max_bytes=p["max_file_mb"] * _MB, max_uncompressed_bytes=p["max_uncompressed_mb"] * _MB, max_rows=p["max_rows"])


def excel_error(exc: ExcelFileError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=error_detail(exc.code, **exc.params))


async def read_upload(file: UploadFile, file_limits: Limits) -> bytes:
    """The uploaded bytes, read up to one byte over the limit (a larger
    file is refused without reading the rest)."""
    data = await file.read(file_limits.max_bytes + 1)
    if len(data) > file_limits.max_bytes:
        raise excel_error(ExcelFileError("excel_too_large", max_mb=file_limits.max_bytes // _MB))
    return data


def staging_path(job_id: uuid.UUID) -> Path:
    return backend_path(get_settings().import_staging_dir) / f"{job_id}.xlsx"


async def start(
    db: AsyncSession,
    *,
    target: ImportTarget,
    params: dict[str, Any],
    user: User,
    file_name: str | None,
    data: bytes,
    material_id: uuid.UUID | None = None,
) -> ImportJob:
    name = PurePath(file_name or "").name
    if len(name) > _FILE_NAME_MAX:
        raise excel_error(ExcelFileError("excel_file_name_too_long", max=_FILE_NAME_MAX))
    try:
        check_upload(name, data, await limits(db))
    except ExcelFileError as exc:
        raise excel_error(exc) from None
    job = ImportJob(
        id=uuid.uuid4(),
        template=target.kind,
        params=params,
        user_id=user.id,
        material_id=material_id,
        status="analyzing",
        file_name=name,
        file_sha256=hashlib.sha256(data).hexdigest(),
        counts={},
    )
    path = staging_path(job.id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    db.add(job)
    await db.commit()
    return job


async def run_analysis(job_id: uuid.UUID) -> None:
    """The background half of phase 1 (see the module docstring)."""
    path = staging_path(job_id)
    async with async_session_factory() as db:
        job = await db.get(ImportJob, job_id)
        if job is None or job.status != "analyzing":
            return
        try:
            target = get_target(job.template)
            template = await target.template(db, job.params)
            read = await asyncio.to_thread(read_rows, template, path.read_bytes(), await limits(db))
            own_analysis = getattr(target, "analyze", None)
            if own_analysis is not None:
                report = await own_analysis(db, job.params, template, read)
            else:
                stored = await target.stored(db, job.params, template)
                references = {t: await codes_by_state(db, t) for t in {c.ref_table for c in template.columns if c.ref_table}}
                report = analyze(template, read, stored, references)
            outcome = {"status": "analyzed", "report": report, "counts": report["counts"], "analyzed_at": datetime.now(timezone.utc)}
        except ExcelFileError as exc:
            outcome = {"status": "failed", "error_code": exc.code, "report": {"error_params": exc.params}}
        except Exception:
            ref = new_error_ref()
            logger.exception("ref=%s import job %s: the analysis failed", ref, job_id, extra={"ref": ref})
            outcome = {"status": "failed", "error_code": "import_failed", "report": {"error_params": {"ref": ref}}}
        finally:
            path.unlink(missing_ok=True)
        await db.rollback()
        # Only over a job still "analyzing": one reaped meanwhile (it took
        # longer than import.stale_minutes) stays failed, as the person was told.
        await db.execute(update(ImportJob).where(ImportJob.id == job_id, ImportJob.status == "analyzing").values(**outcome))
        await db.commit()


async def reap_if_stale(db: AsyncSession, job: ImportJob) -> ImportJob:
    if job.status != "analyzing":
        return job
    minutes = (await get_parameter(db, "import"))["stale_minutes"]
    if datetime.now(timezone.utc) - job.created_at > timedelta(minutes=minutes):
        job.status, job.error_code = "failed", "import_interrupted"
        await db.commit()
        await db.refresh(job)
        staging_path(job.id).unlink(missing_ok=True)
    return job


def job_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_detail("import_job_not_found"))


async def get_job(db: AsyncSession, job_id: uuid.UUID, user: User, *, for_update: bool = False) -> ImportJob:
    """The job, if `user` started it (or is an admin); 404 otherwise."""
    query = select(ImportJob).where(ImportJob.id == job_id)
    job = (await db.execute(query.with_for_update() if for_update else query)).scalar_one_or_none()
    if job is None or (job.user_id != user.id and not user.is_admin):
        raise job_not_found()
    return job


def _conflict(code: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_detail(code))


async def apply(db: AsyncSession, job_id: uuid.UUID, user: User, ip: str | None) -> ImportJob:
    job = await reap_if_stale(db, await get_job(db, job_id, user, for_update=True))
    target = get_target(job.template)
    if not target.can_import(user, job.params):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_detail("import_not_allowed"))
    if job.status == "applied":
        raise _conflict("import_already_applied")
    if job.status != "analyzed":
        raise _conflict("import_not_analyzed")
    if job.counts.get("errors"):
        raise _conflict("import_has_errors")
    template = await target.template(db, job.params)
    if job.report.get("template_fields") != [c.field for c in template.columns]:
        # The template changed since the analysis (a table's attributes).
        raise _conflict("import_template_changed")
    await target.apply(db, job, template, user, ip)
    job.status, job.applied_at = "applied", datetime.now(timezone.utc)
    audit.record(
        db,
        action="import.applied",
        entity_type="import_job",
        entity_id=str(job.id),
        user_id=user.id,
        material_id=job.material_id,
        after={"template": job.template, "params": job.params, "file_name": job.file_name, "counts": job.counts},
        ip=ip,
    )
    await db.commit()
    after = getattr(target, "after_apply", None)
    if after is not None:
        # The import is committed: a failure here is logged, never a 500
        # that would make the person retry an import already applied.
        try:
            await after(db, job)
            await db.commit()
        except Exception:
            ref = new_error_ref()
            logger.exception("ref=%s import job %s: after_apply failed", ref, job.id, extra={"ref": ref})
            await db.rollback()
    await db.refresh(job)
    return job
