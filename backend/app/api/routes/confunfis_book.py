"""The CONFUNFIS book of a CUF (E15, NT 10/17 Anexo XI): import it (two
phases, app/services/anexo_xi_import.py) and export it as the Anexo XI,
the "Libro AAL" or the empty template for a subcontractor
(app/services/anexo_xi_export.py).

Permissions (D5): exporting needs confunfis.ver; importing in "Fusionar",
confunfis.editar; "Sustituir", the admin. Applying takes the confirmations
the analysis asked for: a CUF in the file other than the material's, and
the CUF's name typed for "Sustituir".
"""

import re
import uuid
from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, Request, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, require_material_permission
from app.api.routes.catalog import XLSX
from app.api.routes.imports import job_out
from app.core.errors import error_detail
from app.db.base import get_db
from app.io_excel.targets import get_target
from app.models import User
from app.schemas.common import StrictModel
from app.schemas.reference import ImportJobOut
from app.services import import_jobs
from app.services.anexo_xi_export import AAL, ANEXO, PLANTILLA, build_book
from app.services.anexo_xi_import import ANEXO_XI, MERGE, REPLACE
from app.services.permissions import MaterialAccess
from app.services.snapshots import client_ip

router = APIRouter(prefix="/api/materials/{material_id}/confunfis", tags=["confunfis"])

READ, EDIT = "confunfis.ver", "confunfis.editar"
_FILE_NAMES = {ANEXO: "ANEXO_XI", AAL: "LIBRO_AAL", PLANTILLA: "PLANTILLA_CONFUNFIS"}


class ApplyBookIn(StrictModel):
    # The file's CUF is not this material's: applied only when confirmed.
    confirm_cuf: bool = False
    # "Sustituir": the CUF's name, typed.
    confirm_name: str | None = None


def _forbidden_replace() -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_detail("import_replace_admin_only"))


@router.post("/import", response_model=ImportJobOut, status_code=status.HTTP_202_ACCEPTED)
async def import_book(
    background: BackgroundTasks,
    mode: str = Query(default=MERGE, pattern=f"^({MERGE}|{REPLACE})$"),
    file: UploadFile = File(...),
    access: MaterialAccess = Depends(require_material_permission(EDIT)),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> ImportJobOut:
    """Phase 1: the book analysed in the background against this CUF; poll
    GET /api/import-jobs/{id}, then apply it here."""
    if mode == REPLACE and not user.is_admin:
        raise _forbidden_replace()
    data = await import_jobs.read_upload(file, await import_jobs.limits(db))
    job = await import_jobs.start(
        db, target=get_target(ANEXO_XI), params={"material_id": str(access.material.id), "mode": mode, "user_id": str(user.id)}, user=user,
        file_name=file.filename, data=data, material_id=access.material.id,
    )
    background.add_task(import_jobs.run_analysis, job.id)
    return job_out(job)


@router.post("/import/{job_id}/apply", response_model=ImportJobOut)
async def apply_book(
    job_id: uuid.UUID, body: ApplyBookIn, request: Request,
    access: MaterialAccess = Depends(require_material_permission(EDIT)), user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
) -> ImportJobOut:
    job = await import_jobs.get_job(db, job_id, user, for_update=True)
    if job.template != ANEXO_XI or job.params.get("material_id") != str(access.material.id):
        raise import_jobs.job_not_found()
    if job.params.get("mode") == REPLACE and not user.is_admin:
        raise _forbidden_replace()
    # A new dict: the JSONB column sees the change.
    job.params = {**job.params, "confirm_cuf": body.confirm_cuf, "confirm_name": body.confirm_name}
    await db.flush()
    return job_out(await import_jobs.apply(db, job.id, user, client_ip(request)))


def _file_name(kind: str, name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_")[:60] or "CUF"
    return f"{_FILE_NAMES[kind]}_{safe}_{date.today():%Y%m%d}.xlsx"


@router.get("/export")
async def export_book(
    kind: str = Query(default=ANEXO, pattern=f"^({ANEXO}|{AAL}|{PLANTILLA})$"),
    access: MaterialAccess = Depends(require_material_permission(READ)),
    db: AsyncSession = Depends(get_db),
) -> Response:
    data = await build_book(db, access.material, kind)
    return Response(content=data, media_type=XLSX, headers={"Content-Disposition": f'attachment; filename="{_file_name(kind, access.material.name)}"'})
