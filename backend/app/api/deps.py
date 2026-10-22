"""Authentication and authorization dependencies (D4/D5). Always checked
on the server: the frontend hides what a user may not do, the backend
refuses it.

- get_session_user: a valid access token of an active user (may still have
  to change their password).
- current_user: the same, and the password change already done.
- require_admin: a global admin.
- require_material_permission("confunfis.editar"): the material of the
  route's {material_id}, and that permission on it. A material the user
  has no access to (or that does not exist) is a 404, never a 403, so its
  existence is not revealed; a material they are in but without the
  permission is a 403.
"""

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import error_detail
from app.core.security import InvalidAccessToken, access_token_subject
from app.db.base import get_db
from app.models import User
from app.services.permissions import MaterialAccess, material_access

_bearer = HTTPBearer(auto_error=False)


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=error_detail("not_authenticated"),
        headers={"WWW-Authenticate": "Bearer"},
    )


def material_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_detail("material_not_found"))


async def get_session_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    """The user of the access token. Any problem (none, expired, another
    key, a deleted or deactivated user) is the same 401."""
    if credentials is None:
        raise _unauthorized()
    try:
        user_id = access_token_subject(credentials.credentials)
    except InvalidAccessToken:
        raise _unauthorized() from None
    user = await db.get(User, user_id)
    if user is None or user.deleted_at is not None or not user.is_active:
        raise _unauthorized()
    return user


async def current_user(user: User = Depends(get_session_user)) -> User:
    """A signed-in user who has no pending password change. Until they
    change it (a new account, a reset), only /api/auth/* and
    /api/me/password answer them."""
    if user.must_change_password:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_detail("password_change_required"))
    return user


async def require_admin(user: User = Depends(current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_detail("admin_required"))
    return user


def require_material_permission(permission: str):
    """Dependency factory: the route's {material_id} must be a material the
    user has `permission` on. Returns the MaterialAccess."""

    async def dependency(
        material_id: uuid.UUID,
        user: User = Depends(current_user),
        db: AsyncSession = Depends(get_db),
    ) -> MaterialAccess:
        access = await material_access(db, user, material_id)
        if access is None:
            raise material_not_found()
        if not access.can(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=error_detail("permission_denied", permission=permission),
            )
        return access

    return dependency
