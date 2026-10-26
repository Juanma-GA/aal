"""The signed-in user's own account: password and interface preferences."""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, get_session_user, material_not_found
from app.api.routes.auth import me_out, set_refresh_cookie, token_response
from app.core.errors import error_detail
from app.core.merge import deep_merge
from app.core.security import hash_password, verify_password
from app.db.base import get_db
from app.models import User
from app.schemas.auth import MeOut, PasswordChange, TokenResponse, UiPreferencesPatch
from app.services import audit, sessions
from app.services.parameters import get_parameter
from app.services.password_policy import check_new_password
from app.services.permissions import material_access
from app.services.snapshots import client_ip

router = APIRouter(prefix="/api/me", tags=["me"])


@router.post("/password", response_model=TokenResponse)
async def change_password(
    body: PasswordChange,
    request: Request,
    response: Response,
    user: User = Depends(get_session_user),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Allowed with a pending change (that is what it is for). Ends every
    session of the user and opens a new one for the caller: the answer
    carries its access token and sets its refresh cookie. (The old cookie
    never reaches this route: its Path is /api/auth.)"""
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_detail("current_password_incorrect"))
    params = await get_parameter(db, "auth")
    check_new_password(body.new_password, params["password"])
    if body.new_password == body.current_password:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=error_detail("password_unchanged"))
    before = {"must_change_password": user.must_change_password}
    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False
    user.version += 1
    await sessions.end_user_sessions(db, user.id, "password_changed")
    issued = sessions.issue(db, user, timedelta(days=params["refresh_token_days"]))
    audit.record(
        db,
        action="user.password_changed",
        entity_type="user",
        entity_id=str(user.id),
        user_id=user.id,
        before=before,
        after={"must_change_password": False},
        ip=client_ip(request),
    )
    await db.commit()
    set_refresh_cookie(response, issued, params["refresh_token_days"])
    return token_response(user, params)


@router.put("/ui-preferences", response_model=MeOut)
async def update_ui_preferences(
    body: UiPreferencesPatch,
    request: Request,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> MeOut:
    """Deep-merges the keys sent over the stored preferences (HR10); the row
    is locked meanwhile, so two tabs never lose each other's keys."""
    patch = body.model_dump(mode="json", exclude_unset=True)
    ui = await get_parameter(db, "ui")
    for key, code in (("sidebar_width", "sidebar_width_out_of_range"), ("detail_panel_width", "detail_panel_width_out_of_range")):
        if patch.get(key) is not None:
            limits = ui[key]
            if not limits["min"] <= patch[key] <= limits["max"]:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=error_detail(code, min=limits["min"], max=limits["max"]))
    if patch.get("active_material_id") is not None:
        if await material_access(db, user, body.active_material_id) is None:
            raise material_not_found()
    locked = (await db.execute(select(User).where(User.id == user.id).with_for_update())).scalar_one()
    before = dict(locked.ui_preferences or {})
    locked.ui_preferences = deep_merge(before, patch)
    audit.record(
        db,
        action="user.ui_preferences_updated",
        entity_type="user",
        entity_id=str(user.id),
        user_id=user.id,
        before=before,
        after=locked.ui_preferences,
        ip=client_ip(request),
    )
    await db.commit()
    await db.refresh(locked)
    return me_out(locked)


@router.get("/ui-settings")
async def ui_settings(_user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> dict:
    """The interface limits every user needs (the "ui" parameter)."""
    return await get_parameter(db, "ui")
