"""The PALI module catalog (E02): the menu, each module's card, and the
admin's change of a module's status and route."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, require_admin
from app.api.routes.users import version_conflict
from app.core.errors import error_detail
from app.db.base import get_db
from app.models import MODULE_STATUSES, ModuleCatalog, ModuleGroup, ModuleRequirement, User
from app.schemas.modules import ModuleBrief, ModuleDetail, ModuleGroupOut, ModuleLink, ModuleUpdate, RequirementOut
from app.services import audit
from app.services.module_catalog import check_route
from app.services.snapshots import client_ip

router = APIRouter(prefix="/api/modules", tags=["modules"])


def _brief(m: ModuleCatalog) -> ModuleBrief:
    return ModuleBrief(code=m.code, name=m.name, sort_order=m.sort_order, phase=m.phase, status=m.status, route=m.route, version=m.version)


def _link(m: ModuleCatalog) -> ModuleLink:
    return ModuleLink(code=m.code, name=m.name, status=m.status, group_code=m.group_code)


def _snapshot(m: ModuleCatalog) -> dict:
    return {"code": m.code, "status": m.status, "route": m.route}


def module_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_detail("module_not_found"))


@router.get("", response_model=list[ModuleGroupOut])
async def list_modules(_user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> list[ModuleGroupOut]:
    groups = (await db.execute(select(ModuleGroup).order_by(ModuleGroup.sort_order))).scalars().all()
    modules = (await db.execute(select(ModuleCatalog).order_by(ModuleCatalog.sort_order, ModuleCatalog.code))).scalars().all()
    return [
        ModuleGroupOut(code=g.code, name=g.name, sort_order=g.sort_order, modules=[_brief(m) for m in modules if m.group_code == g.code])
        for g in groups
    ]


async def _detail(db: AsyncSession, module: ModuleCatalog) -> ModuleDetail:
    everything = {m.code: m for m in (await db.execute(select(ModuleCatalog))).scalars().all()}
    group = await db.get(ModuleGroup, module.group_code)
    requirements = (
        await db.execute(
            select(ModuleRequirement).where(ModuleRequirement.module_code == module.code).order_by(ModuleRequirement.sort_order)
        )
    ).scalars().all()
    used_by = sorted((m for m in everything.values() if module.code in m.dependencies), key=lambda m: m.sort_order)
    return ModuleDetail(
        **_brief(module).model_dump(),
        group_code=module.group_code,
        group_name=group.name if group else module.group_code,
        encargo=module.encargo,
        objective=module.objective,
        inputs=module.inputs,
        outputs=module.outputs,
        deliverable=module.deliverable,
        requirements=[RequirementOut(rf_id=r.rf_id, text=r.text) for r in requirements],
        depends_on=[_link(everything[c]) for c in module.dependencies if c in everything],
        used_by=[_link(m) for m in used_by],
    )


@router.get("/{code}", response_model=ModuleDetail)
async def get_module(code: str, _user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> ModuleDetail:
    module = await db.get(ModuleCatalog, code)
    if module is None:
        raise module_not_found()
    return await _detail(db, module)


@router.patch("/{code}", response_model=ModuleDetail)
async def update_module(
    code: str,
    body: ModuleUpdate,
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> ModuleDetail:
    """Status and route (only a "disponible" module has one; changing to
    another state clears it). Carries the version it read (D10)."""
    module = (await db.execute(select(ModuleCatalog).where(ModuleCatalog.code == code).with_for_update())).scalar_one_or_none()
    if module is None:
        raise module_not_found()
    if module.version != body.version:
        raise version_conflict(module.version)
    changes = body.model_dump(exclude_unset=True, exclude={"version"})
    new_status = changes.get("status") or module.status
    if new_status not in MODULE_STATUSES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=error_detail("module_status_unknown"))
    new_route = changes["route"] if "route" in changes else module.route
    if new_status != "disponible":
        new_route = None
    elif not new_route:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=error_detail("module_route_required"))
    elif check_route(new_route):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=error_detail("module_route_invalid"))
    before = _snapshot(module)
    module.status = new_status
    module.route = new_route
    module.version += 1
    audit.record(
        db, action="module.updated", entity_type="module", entity_id=module.code, user_id=admin.id, before=before, after=_snapshot(module), ip=client_ip(request)
    )
    await db.commit()
    await db.refresh(module)
    return await _detail(db, module)
