"""Requests for a new SNS (E11, NT §9.1.1): the function of a component of
the CUF is not in its normalized configuration. Whoever edits the material
(material.editar) drafts, edits and sends them; an admin accepts or rejects
a sent one with an answer. Every step carries the version it read (D10) and
is audited. A draft may be discarded (?confirm=true, soft delete: HR9). The
sent ones are exported to Excel to send them to JIMALE."""

import asyncio
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, require_admin, require_material_permission
from app.api.routes.catalog import XLSX
from app.api.routes.materials import _active_material
from app.api.routes.users import confirmation_required, version_conflict
from app.core.errors import error_detail
from app.db.base import get_db
from app.io_excel.template import Column, Template
from app.io_excel.writer import write_workbook
from app.models import SnsRequest, User
from app.schemas.cuf import SnsRequestAnnul, SnsRequestIn, SnsRequestOut, SnsRequestResolve, SnsRequestStep, SnsRequestUpdate
from app.services import audit
from app.services.permissions import MaterialAccess
from app.services.snapshots import client_ip

router = APIRouter(prefix="/api/materials/{material_id}/sns-requests", tags=["sns-requests"])

EXPORT = Template(
    code="sns_requests",
    sheet="SOLICITUDES SNS",
    unique_keys=False,
    columns=(
        Column("cuf", ("CUF",), width=30),
        Column("noc", ("NOC",), width=16),
        Column("proposed_sns", ("SNS PROPUESTO",), key=True, width=14),
        Column("parent_sns", ("SNS PADRE",), width=12),
        Column("name", ("NOMBRE",), width=40),
        Column("function", ("FUNCIÓN / DESCRIPCIÓN",), width=60),
        Column("justification", ("JUSTIFICACIÓN",), width=60),
        Column("sent_at", ("FECHA DE ENVÍO",), width=16),
        Column("created_by", ("SOLICITANTE",), width=30),
    ),
)


def _snapshot(r: SnsRequest) -> dict:
    return {
        "proposed_sns": r.proposed_sns, "parent_sns": r.parent_sns, "name": r.name, "function": r.function,
        "justification": r.justification, "state": r.state, "response": r.response,
        **({"annulled": True, "annul_reason": r.annul_reason} if r.annulled_at else {}),
    }


async def _names(db: AsyncSession, ids: set[uuid.UUID | None]) -> dict[uuid.UUID, str]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    return dict((await db.execute(select(User.id, User.display_name).where(User.id.in_(ids)))).all())


def _out(r: SnsRequest, names: dict[uuid.UUID, str]) -> SnsRequestOut:
    return SnsRequestOut(
        id=r.id, proposed_sns=r.proposed_sns, parent_sns=r.parent_sns, name=r.name, function=r.function, justification=r.justification,
        state=r.state, response=r.response, created_by=names.get(r.created_by), resolved_by=names.get(r.resolved_by),
        created_at=r.created_at, sent_at=r.sent_at, resolved_at=r.resolved_at, version=r.version,
        created_by_id=r.created_by, annulled_at=r.annulled_at, annulled_by=names.get(r.annulled_by), annul_reason=r.annul_reason,
    )


async def _one(db: AsyncSession, material_id: uuid.UUID, request_id: uuid.UUID, version: int) -> SnsRequest:
    found = (
        await db.execute(
            select(SnsRequest).where(SnsRequest.id == request_id, SnsRequest.material_id == material_id, SnsRequest.deleted_at.is_(None)).with_for_update()
        )
    ).scalar_one_or_none()
    if found is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_detail("sns_request_not_found"))
    if found.version != version:
        raise version_conflict(found.version)
    return found


def _wrong_state(state: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_detail("sns_request_wrong_state", state=state))


async def _saved(db: AsyncSession, r: SnsRequest, user: User, action: str, before: dict | None, request: Request) -> SnsRequestOut:
    audit.record(
        db, action=action, entity_type="sns_request", entity_id=str(r.id), user_id=user.id, material_id=r.material_id,
        before=before, after=_snapshot(r), ip=client_ip(request),
    )
    await db.commit()
    await db.refresh(r)
    return _out(r, await _names(db, {r.created_by, r.resolved_by}))


@router.get("", response_model=list[SnsRequestOut])
async def list_requests(
    material_id: uuid.UUID,
    annulled: bool = False,
    _access: MaterialAccess = Depends(require_material_permission("material.ver")),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SnsRequestOut]:
    """The live requests; `annulled=true` (an admin's "Mostrar anuladas")
    adds the annulled ones. A discarded draft never comes back."""
    visible = SnsRequest.deleted_at.is_(None)
    if annulled:
        if not user.is_admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_detail("admin_required"))
        visible = or_(visible, SnsRequest.annulled_at.is_not(None))
    rows = (
        await db.execute(select(SnsRequest).where(SnsRequest.material_id == material_id, visible).order_by(SnsRequest.created_at.desc()))
    ).scalars().all()
    names = await _names(db, {r.created_by for r in rows} | {r.resolved_by for r in rows} | {r.annulled_by for r in rows})
    return [_out(r, names) for r in rows]


@router.post("", response_model=SnsRequestOut, status_code=status.HTTP_201_CREATED)
async def create_request(
    material_id: uuid.UUID,
    body: SnsRequestIn,
    request: Request,
    _access: MaterialAccess = Depends(require_material_permission("material.editar")),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> SnsRequestOut:
    r = SnsRequest(material_id=material_id, state="borrador", created_by=user.id, version=1, **body.model_dump())
    db.add(r)
    await db.flush()
    return await _saved(db, r, user, "sns_request.created", None, request)


@router.patch("/{request_id}", response_model=SnsRequestOut)
async def update_request(
    material_id: uuid.UUID,
    request_id: uuid.UUID,
    body: SnsRequestUpdate,
    request: Request,
    _access: MaterialAccess = Depends(require_material_permission("material.editar")),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> SnsRequestOut:
    """Only a draft is edited."""
    r = await _one(db, material_id, request_id, body.version)
    if r.state != "borrador":
        raise _wrong_state(r.state)
    before = _snapshot(r)
    for name, value in body.model_dump(exclude={"version"}).items():
        setattr(r, name, value)
    r.version += 1
    return await _saved(db, r, user, "sns_request.updated", before, request)


@router.post("/{request_id}/submit", response_model=SnsRequestOut)
async def submit_request(
    material_id: uuid.UUID,
    request_id: uuid.UUID,
    body: SnsRequestStep,
    request: Request,
    _access: MaterialAccess = Depends(require_material_permission("material.editar")),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> SnsRequestOut:
    r = await _one(db, material_id, request_id, body.version)
    if r.state != "borrador":
        raise _wrong_state(r.state)
    before = _snapshot(r)
    r.state, r.sent_at = "enviada", datetime.now(UTC)
    r.version += 1
    return await _saved(db, r, user, "sns_request.sent", before, request)


@router.post("/{request_id}/resolve", response_model=SnsRequestOut)
async def resolve_request(
    material_id: uuid.UUID,
    request_id: uuid.UUID,
    body: SnsRequestResolve,
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> SnsRequestOut:
    """An admin accepts or rejects a sent request, with an answer."""
    await _active_material(db, material_id)  # not of a deleted material
    r = await _one(db, material_id, request_id, body.version)
    if r.state != "enviada":
        raise _wrong_state(r.state)
    before = _snapshot(r)
    r.state, r.response, r.resolved_by, r.resolved_at = body.decision, body.response, admin.id, datetime.now(UTC)
    r.version += 1
    return await _saved(db, r, admin, f"sns_request.{'accepted' if body.decision == 'aceptada' else 'rejected'}", before, request)


@router.delete("/{request_id}", status_code=status.HTTP_204_NO_CONTENT)
async def discard_request(
    material_id: uuid.UUID,
    request_id: uuid.UUID,
    version: int,
    request: Request,
    confirm: bool = False,
    access: MaterialAccess = Depends(require_material_permission("material.ver")),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """A draft only, never sent, by its author or whoever edits the
    material; it is kept, marked deleted (HR9). A sent one is annulled."""
    if not confirm:
        raise confirmation_required()
    r = await _one(db, material_id, request_id, version)
    if r.created_by != user.id and not access.can("material.editar"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_detail("permission_denied", permission="material.editar"))
    if r.state != "borrador":
        raise _wrong_state(r.state)
    before = _snapshot(r)
    r.deleted_at = datetime.now(UTC)
    r.version += 1
    audit.record(
        db, action="sns_request.discarded", entity_type="sns_request", entity_id=str(r.id), user_id=user.id, material_id=material_id,
        before=before, after=None, ip=client_ip(request),
    )
    await db.commit()


@router.post("/{request_id}/annul", status_code=status.HTTP_204_NO_CONTENT)
async def annul_request(
    material_id: uuid.UUID,
    request_id: uuid.UUID,
    body: SnsRequestAnnul,
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    """An admin annuls a sent, accepted or rejected request, with a reason:
    it leaves the list and the export (HR9: kept, and in the audit)."""
    await _active_material(db, material_id)
    r = await _one(db, material_id, request_id, body.version)
    if r.state == "borrador":
        raise _wrong_state(r.state)
    before = _snapshot(r)
    now = datetime.now(UTC)
    r.deleted_at, r.annulled_at, r.annulled_by, r.annul_reason = now, now, admin.id, body.reason
    r.version += 1
    audit.record(
        db, action="sns_request.annulled", entity_type="sns_request", entity_id=str(r.id), user_id=admin.id, material_id=material_id,
        before=before, after=_snapshot(r), ip=client_ip(request),
    )
    await db.commit()


@router.get("/export")
async def export_requests(
    material_id: uuid.UUID, access: MaterialAccess = Depends(require_material_permission("material.ver")), db: AsyncSession = Depends(get_db)
) -> Response:
    """The sent requests (waiting for JIMALE), to send them."""
    material = access.material
    rows = (
        await db.execute(
            select(SnsRequest).where(SnsRequest.material_id == material_id, SnsRequest.state == "enviada", SnsRequest.deleted_at.is_(None)).order_by(SnsRequest.sent_at)
        )
    ).scalars().all()
    names = await _names(db, {r.created_by for r in rows})
    data = await asyncio.to_thread(
        write_workbook,
        EXPORT,
        [
            {
                "cuf": material.name, "noc": material.noc, "proposed_sns": r.proposed_sns, "parent_sns": r.parent_sns, "name": r.name,
                "function": r.function or None, "justification": r.justification,
                "sent_at": r.sent_at.strftime("%Y%m%d") if r.sent_at else None, "created_by": names.get(r.created_by),
            }
            for r in rows
        ],
    )
    return Response(content=data, media_type=XLSX, headers={"Content-Disposition": f'attachment; filename="SOLICITUDES_SNS_{material.noc or material.id}.xlsx"'})
