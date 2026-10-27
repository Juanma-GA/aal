"""The NT 10/17 validator (E16, RF-03).

- `/api/validation-rules`: the rules and their configuration (read by
  anyone; changed by the admin, audited with its version: every run made
  with another configuration is "desactualizado").
- `/api/materials/{id}/validation`: the latest validation of a CUF (its
  traffic light, its findings, why the delivery is refused), "Validar
  ahora" (validacion.ejecutar; reading it, validacion.ver), accepting a warning (confunfis.editar, with a
  justification) and the report as Excel or PDF.
- `/api/materials/{id}/confunfis/delivery`: "Exportar para entrega" (confunfis.entregar) -- the
  CUF's Anexo XI and the Fichero Carga of its articles, refused (409, with
  the reasons) without an up-to-date validation free of blocking findings.
"""

import io
import re
import uuid
import zipfile
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, require_admin, require_material_permission
from app.api.routes.catalog import XLSX
from app.core.errors import error_detail
from app.db.base import get_db
from app.models import Article, ArticleFieldDefinition, FindingAcceptance, Material, User, ValidationFinding, ValidationRule
from app.schemas.validation import AcceptIn, FindingOut, RuleCount, RuleOut, RuleUpdate, ValidationOut
from app.services import audit, validation, validation_report
from app.io_excel.writer import write_workbook
from app.services.anexo_xi_export import ANEXO, build_book
from app.services.article_import import FICHERO_CARGA, build_template, export_values
from app.services.articles import Checker
from app.services.permissions import MaterialAccess
from app.services.snapshots import client_ip
from app.validacion.catalog import BY_CODE, CATALOG

rules_router = APIRouter(prefix="/api/validation-rules", tags=["validation"])
router = APIRouter(prefix="/api/materials/{material_id}", tags=["validation"])

# E17 fleco 1: reading the report is validacion.ver (everyone); running it, validacion.ejecutar
# (not the observer); accepting a warning, confunfis.editar.
READ, RUN, EDIT = "validacion.ver", "validacion.ejecutar", "confunfis.editar"
# E17 fleco 2: the delivery has its own permission (the working exports stay "exportar").
DELIVER = "confunfis.entregar"


def _rule_out(r: ValidationRule) -> RuleOut:
    info = BY_CODE[r.code]
    return RuleOut(
        code=r.code, scope=r.scope, ref=info.ref, active=r.active, severity=r.severity, default_severity=info.severity, params=r.params,
        help=r.help, version=r.version, updated_at=r.updated_at,
    )


@rules_router.get("", response_model=list[RuleOut])
async def list_rules(_user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> list[RuleOut]:
    rules = await validation.settings(db)
    return [_rule_out(rules[info.code]) for info in CATALOG if info.code in rules]


@rules_router.patch("/{code}", response_model=RuleOut)
async def update_rule(code: str, body: RuleUpdate, request: Request, user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)) -> RuleOut:
    rule = (await db.execute(select(ValidationRule).where(ValidationRule.code == code).with_for_update())).scalar_one_or_none()
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_detail("validation_rule_not_found"))
    if rule.version != body.version:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_detail("version_conflict", current=rule.version))
    defaults = BY_CODE[code].params
    unknown = set(body.params or {}) - set(defaults)
    if unknown:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=error_detail("validation_rule_param_unknown", params=", ".join(sorted(unknown))))
    # A value of another type (or a huge one) would break every validation (HR7): the catalog's type, at most 200 characters.
    wrong = sorted(k for k, v in (body.params or {}).items() if type(v) is not type(defaults[k]) or len(str(v)) > 200)
    if wrong:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=error_detail("validation_rule_param_invalid", params=", ".join(wrong)))
    before = {"active": rule.active, "severity": rule.severity, "params": rule.params, "help": rule.help}
    sent = body.model_fields_set
    if "active" in sent and body.active is not None:
        rule.active = body.active
    if "severity" in sent and body.severity is not None:
        rule.severity = body.severity
    if "params" in sent and body.params is not None:
        rule.params = {**BY_CODE[code].params, **body.params}
    if "help" in sent:
        rule.help = (body.help or "").strip() or None
    rule.version += 1
    rule.updated_by = user.id
    audit.record(
        db, action="validation.rule_updated", entity_type="validation_rule", entity_id=code, user_id=user.id,
        before=before, after={"active": rule.active, "severity": rule.severity, "params": rule.params, "help": rule.help}, ip=client_ip(request),
    )
    await db.commit()
    await db.refresh(rule)
    return _rule_out(rule)


async def _names(db: AsyncSession, ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    ids = {i for i in ids if i}
    return dict((await db.execute(select(User.id, User.display_name).where(User.id.in_(ids)))).all()) if ids else {}


async def _acceptances(db: AsyncSession, findings: list[ValidationFinding]) -> dict[uuid.UUID, FindingAcceptance]:
    ids = {f.acceptance_id for f in findings if f.acceptance_id}
    return {a.id: a for a in (await db.execute(select(FindingAcceptance).where(FindingAcceptance.id.in_(ids)))).scalars()} if ids else {}


async def _validation_out(db: AsyncSession, material: Material) -> ValidationOut:
    run = await validation.latest(db, material)
    problems = await validation.delivery_problems(db, material)
    if run is None:
        return ValidationOut(state="none", outdated=False, outdated_data=False, outdated_rules=False, delivery_problems=problems)
    stale = await validation.outdated(db, material, run)
    found = await validation.findings(db, run)
    accepted = await _acceptances(db, found)
    names = await _names(db, {run.user_id, *(a.created_by for a in accepted.values())})
    by_rule = []
    for info in CATALOG:
        mine = [f for f in found if f.rule_code == info.code]
        if mine:
            by_rule.append(RuleCount(code=info.code, severity=mine[0].severity, ref=info.ref, findings=len(mine), accepted=sum(1 for f in mine if f.acceptance_id)))
    light = validation.summary(run, stale)
    return ValidationOut(
        state=light["state"], outdated=light["outdated"], outdated_data=stale["data"], outdated_rules=stale["rules"], run_id=run.id, at=run.created_at,
        by=names.get(run.user_id), trigger=run.trigger, seconds=run.seconds, blocking=run.blocking, warnings=run.warnings, accepted=run.accepted,
        by_rule=by_rule, delivery_problems=problems,
        findings=[
            FindingOut(
                id=f.id, rule_code=f.rule_code, severity=f.severity, scope=f.scope, entity_type=f.entity_type, entity_id=f.entity_id, problem=f.problem,
                params=f.params, field=f.field, row_id=f.row_id, location=f.location, found=f.found, accepted=f.acceptance_id is not None,
                justification=accepted[f.acceptance_id].justification if f.acceptance_id in accepted else None,
                accepted_by=names.get(accepted[f.acceptance_id].created_by) if f.acceptance_id in accepted else None,
                accepted_at=accepted[f.acceptance_id].created_at if f.acceptance_id in accepted else None,
            )
            for f in found
        ],
    )


@router.get("/validation", response_model=ValidationOut)
async def get_validation(access: MaterialAccess = Depends(require_material_permission(READ)), db: AsyncSession = Depends(get_db)) -> ValidationOut:
    return await _validation_out(db, access.material)


@router.post("/validation", response_model=ValidationOut)
async def run_validation(
    request: Request, access: MaterialAccess = Depends(require_material_permission(RUN)), user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
) -> ValidationOut:
    """"Validar ahora": a full run, kept (the latest is the CUF's state).
    Always run: the fingerprint does not see everything the rules read (the
    CUF mounted in another one, a cycle across the whole master, new rules)."""
    # One validation of a CUF at a time, after any edit that holds it.
    await db.execute(select(Material.id).where(Material.id == access.material.id).with_for_update())
    await validation.validate(db, access.material, user, "manual", client_ip(request))
    await db.commit()
    return await _validation_out(db, access.material)


@router.post("/validation/findings/{finding_id}/accept", response_model=ValidationOut)
async def accept_finding(
    finding_id: uuid.UUID, body: AcceptIn, request: Request,
    access: MaterialAccess = Depends(require_material_permission(EDIT)), user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
) -> ValidationOut:
    run = await validation.latest(db, access.material)
    finding = (await db.execute(select(ValidationFinding).where(ValidationFinding.id == finding_id).with_for_update())).scalar_one_or_none()
    if run is None or finding is None or finding.run_id != run.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_detail("validation_finding_not_found"))
    try:
        await validation.accept(db, access.material, finding, body.justification.strip(), user, client_ip(request))
    except validation.AcceptError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_detail(exc.code)) from None
    await db.commit()
    return await _validation_out(db, access.material)


async def _field_names(db: AsyncSession) -> dict[str, str]:
    return dict((await db.execute(select(ArticleFieldDefinition.prisma_code, ArticleFieldDefinition.name))).all())


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_")[:60] or "CUF"


@router.get("/validation/report")
async def validation_report_file(
    format: str = Query(default="pdf", pattern="^(pdf|xlsx)$"),
    access: MaterialAccess = Depends(require_material_permission(READ)), db: AsyncSession = Depends(get_db),
) -> Response:
    material = access.material
    run = await validation.latest(db, material)
    if run is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_detail("validation_not_run"))
    stale = await validation.outdated(db, material, run)
    found = await validation.findings(db, run)
    accepted = await _acceptances(db, found)
    by = (await _names(db, {run.user_id})).get(run.user_id, "") if run.user_id else ""
    args = (material, run, found, by, stale["data"] or stale["rules"], await _field_names(db), {k: a.justification for k, a in accepted.items()})
    name = f"VALIDACION_NT_{_safe(material.name)}_{date.today():%Y%m%d}"
    if format == "pdf":
        return Response(content=validation_report.pdf(*args), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{name}.pdf"'})
    return Response(content=validation_report.xlsx(*args), media_type=XLSX, headers={"Content-Disposition": f'attachment; filename="{name}.xlsx"'})


@router.get("/confunfis/delivery")
async def delivery(
    request: Request, access: MaterialAccess = Depends(require_material_permission(DELIVER)), user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
) -> Response:
    """The CUF's Anexo XI and the Fichero Carga of its articles (the rows' and their parts'), in a zip."""
    material = access.material
    problems = await validation.delivery_problems(db, material)
    if problems:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_detail("delivery_blocked", problems=problems))
    ctx = await validation.context(db, material)
    ids = set(ctx.cuf_articles) | {p.part_article_id for p in ctx.parts if p.part_article_id}
    articles = (await db.execute(select(Article).where(Article.id.in_(ids), Article.deleted_at.is_(None)).order_by(Article.nombre, Article.noc, Article.id))).scalars().all() if ids else []
    checker = await Checker.load(db)
    carga = write_workbook(build_template(checker.defs, FICHERO_CARGA), [export_values(a, FICHERO_CARGA) for a in articles], [])
    anexo = await build_book(db, material, ANEXO, status=False)
    out = io.BytesIO()
    stem = _safe(material.name)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"ANEXO_XI_{stem}.xlsx", anexo)
        z.writestr(f"FICHERO_CARGA_{stem}.xlsx", carga)
    run = await validation.latest(db, material)
    audit.record(
        db, action="confunfis.delivery_exported", entity_type="material", entity_id=str(material.id), user_id=user.id, material_id=material.id,
        after={"run": str(run.id) if run else None, "articles": len(articles)}, ip=client_ip(request),
    )
    await db.commit()
    return Response(content=out.getvalue(), media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="ENTREGA_{stem}_{date.today():%Y%m%d}.zip"'})

