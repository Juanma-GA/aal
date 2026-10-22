"""Sign in, refresh, sign out and who am I (D4).

The access token goes in the body and the browser keeps it only in memory.
The refresh token goes in a cookie: HttpOnly, Secure (REFRESH_COOKIE_SECURE),
SameSite=Strict and Path=/api/auth, so it only travels to these routes and
no script can read it.
"""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session_user
from app.core.config import get_settings
from app.core.errors import error_detail
from app.core.security import burn_password_check, create_access_token, verify_password
from app.db.base import get_db
from app.models import User
from app.schemas.auth import LoginRequest, MeOut, TokenResponse
from app.services import audit, login_limit, sessions
from app.services.parameters import get_parameter
from app.services.snapshots import client_ip

router = APIRouter(prefix="/api/auth", tags=["auth"])

REFRESH_COOKIE = "aal_refresh"
REFRESH_COOKIE_PATH = "/api/auth"


def normalize_email(email: str) -> str:
    return email.strip().lower()


def set_refresh_cookie(response: Response, issued: sessions.IssuedToken, days: int) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        issued.raw,
        max_age=days * 86400,
        path=REFRESH_COOKIE_PATH,
        secure=get_settings().refresh_cookie_secure,
        httponly=True,
        samesite="strict",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        REFRESH_COOKIE,
        path=REFRESH_COOKIE_PATH,
        secure=get_settings().refresh_cookie_secure,
        httponly=True,
        samesite="strict",
    )


def token_response(user: User, params: dict) -> TokenResponse:
    minutes = params["access_token_minutes"]
    return TokenResponse(access_token=create_access_token(user.id, timedelta(minutes=minutes)), expires_in=minutes * 60)


def me_out(user: User) -> MeOut:
    return MeOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        is_admin=user.is_admin,
        must_change_password=user.must_change_password,
        ui_preferences=user.ui_preferences or {},
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    params = await get_parameter(db, "auth")
    email = normalize_email(body.email)
    ip = client_ip(request)
    lockout = await login_limit.check(db, email, ip, params["login_limit"])
    if lockout is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=error_detail("login_rate_limited", retry_after_minutes=lockout.retry_after_minutes),
            headers={"Retry-After": str(lockout.retry_after_minutes * 60)},
        )
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None:
        burn_password_check(body.password)
    valid = user is not None and verify_password(body.password, user.password_hash)
    # A deactivated or deleted user gets the same answer as a wrong
    # password: nothing tells a stranger which accounts exist.
    if not valid or user.deleted_at is not None or not user.is_active:
        login_limit.record_failure(db, email, ip)
        await db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=error_detail("invalid_credentials"))
    await login_limit.clear(db, email, params["login_limit"])
    issued = sessions.issue(db, user, timedelta(days=params["refresh_token_days"]))
    audit.record(db, action="auth.login", entity_type="user", entity_id=str(user.id), user_id=user.id, ip=ip)
    await db.commit()
    set_refresh_cookie(response, issued, params["refresh_token_days"])
    return token_response(user, params)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(request: Request, response: Response, db: AsyncSession = Depends(get_db)) -> TokenResponse | JSONResponse:
    raw = request.cookies.get(REFRESH_COOKIE)
    if not raw:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=error_detail("session_expired"))
    params = await get_parameter(db, "auth")
    try:
        user, issued = await sessions.rotate(db, raw, timedelta(days=params["refresh_token_days"]))
    except sessions.RefreshRefused as refused:
        if refused.reason == "reuse_detected":
            audit.record(
                db,
                action="auth.refresh_reuse_detected",
                entity_type="user",
                entity_id=str(refused.user_id),
                user_id=refused.user_id,
                after={"family_revoked": str(refused.family_id)},
                ip=client_ip(request),
            )
        await db.commit()
        # Returned, not raised: the response must also clear the cookie.
        refusal = JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": error_detail("session_revoked" if refused.reason == "reuse_detected" else "session_expired")},
        )
        _clear_refresh_cookie(refusal)
        return refusal
    await db.commit()
    set_refresh_cookie(response, issued, params["refresh_token_days"])
    return token_response(user, params)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response, db: AsyncSession = Depends(get_db)) -> None:
    """Ends the session of the cookie (its whole family). Without a valid
    cookie there is nothing to end: still a 204."""
    raw = request.cookies.get(REFRESH_COOKIE)
    if raw:
        stored = await sessions.find(db, raw)
        if stored is not None:
            await sessions.revoke_family(db, stored.family_id, "logout")
            audit.record(
                db, action="auth.logout", entity_type="user", entity_id=str(stored.user_id), user_id=stored.user_id, ip=client_ip(request)
            )
            await db.commit()
    _clear_refresh_cookie(response)


@router.get("/me", response_model=MeOut)
async def me(user: User = Depends(get_session_user)) -> MeOut:
    return me_out(user)
