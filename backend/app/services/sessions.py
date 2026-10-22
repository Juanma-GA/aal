"""Refresh tokens and their families (D4).

- A login starts a family and issues its first token.
- A refresh revokes the token it used (reason "rotated") and issues the
  next one in the same family.
- A token already rotated that comes back means someone kept a copy: the
  whole family is revoked ("reuse_detected") and that session is over for
  everyone holding it.
- Logout revokes the family of the cookie it receives; a password change,
  a reset, a deactivation or a delete revoke the user's families (all, or
  all but the caller's own).

The token row is read with SELECT ... FOR UPDATE, so two refreshes with
the same cookie never both rotate it: the second one sees it rotated.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import generate_refresh_token, hash_refresh_token
from app.models import RefreshToken, User


@dataclass(frozen=True)
class IssuedToken:
    raw: str
    family_id: uuid.UUID
    expires_at: datetime


def issue(db: AsyncSession, user: User, lifetime: timedelta, family_id: uuid.UUID | None = None) -> IssuedToken:
    """Stage a new refresh token (a new family unless one is given)."""
    raw, token_hash = generate_refresh_token()
    family = family_id or uuid.uuid4()
    expires_at = datetime.now(UTC) + lifetime
    db.add(RefreshToken(user_id=user.id, family_id=family, token_hash=token_hash, expires_at=expires_at))
    return IssuedToken(raw=raw, family_id=family, expires_at=expires_at)


class RefreshRefused(Exception):
    """The refresh token does not open a session. `reason`: unknown,
    expired, revoked, reuse_detected, user_unavailable."""

    def __init__(self, reason: str, user_id: uuid.UUID | None = None, family_id: uuid.UUID | None = None):
        super().__init__(reason)
        self.reason = reason
        self.user_id = user_id
        self.family_id = family_id


async def find(db: AsyncSession, raw: str, *, for_update: bool = False) -> RefreshToken | None:
    query = select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw))
    if for_update:
        query = query.with_for_update()
    return (await db.execute(query)).scalar_one_or_none()


async def rotate(db: AsyncSession, raw: str, lifetime: timedelta) -> tuple[User, IssuedToken]:
    """The user and the next token of the family, or RefreshRefused. The
    caller commits (also when refused: a reuse revokes the family)."""
    stored = await find(db, raw, for_update=True)
    if stored is None:
        raise RefreshRefused("unknown")
    now = datetime.now(UTC)
    if stored.revoked_at is not None:
        if stored.revoke_reason == "rotated":
            await revoke_family(db, stored.family_id, "reuse_detected")
            raise RefreshRefused("reuse_detected", stored.user_id, stored.family_id)
        raise RefreshRefused("revoked", stored.user_id, stored.family_id)
    if stored.expires_at <= now:
        raise RefreshRefused("expired", stored.user_id, stored.family_id)
    user = await db.get(User, stored.user_id)
    if user is None or user.deleted_at is not None or not user.is_active:
        await revoke_family(db, stored.family_id, "user_unavailable")
        raise RefreshRefused("user_unavailable", stored.user_id, stored.family_id)
    stored.revoked_at = now
    stored.revoke_reason = "rotated"
    return user, issue(db, user, lifetime, family_id=stored.family_id)


async def revoke_family(db: AsyncSession, family_id: uuid.UUID, reason: str) -> None:
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC), revoke_reason=reason)
    )


async def end_user_sessions(db: AsyncSession, user_id: uuid.UUID, reason: str, *, keep_family: uuid.UUID | None = None) -> None:
    """Revoke every active token of the user (but those of `keep_family`)."""
    conditions = [RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)]
    if keep_family is not None:
        conditions.append(RefreshToken.family_id != keep_family)
    await db.execute(update(RefreshToken).where(*conditions).values(revoked_at=datetime.now(UTC), revoke_reason=reason))
