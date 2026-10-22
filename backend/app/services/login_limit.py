"""The limit on failed logins, per email and per client address (E01).

Counted in the database (login_failure) over the last `window_minutes`
(parameter "auth.login_limit"), so it holds across restarts and several
server processes. At the limit the login is refused with 429 and the
minutes until it is allowed again; a correct password does not get in
meanwhile. A successful login clears the email's failures.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import ceil

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LoginFailure


@dataclass(frozen=True)
class Lockout:
    retry_after_minutes: int


async def _oldest_counted(db: AsyncSession, condition, since: datetime, limit: int) -> datetime | None:
    """When the failure that makes the count reach `limit` stops counting:
    None while under the limit."""
    count = await db.scalar(select(func.count()).select_from(LoginFailure).where(condition, LoginFailure.created_at > since))
    if (count or 0) < limit:
        return None
    rows = (
        await db.execute(
            select(LoginFailure.created_at)
            .where(condition, LoginFailure.created_at > since)
            .order_by(LoginFailure.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return rows[-1]


async def check(db: AsyncSession, email: str, ip: str | None, settings: dict) -> Lockout | None:
    window = timedelta(minutes=settings["window_minutes"])
    now = datetime.now(UTC)
    since = now - window
    until = []
    oldest = await _oldest_counted(db, LoginFailure.email == email, since, settings["max_failures_per_email"])
    if oldest is not None:
        until.append(oldest + window)
    if ip is not None:
        oldest = await _oldest_counted(db, LoginFailure.ip == ip, since, settings["max_failures_per_ip"])
        if oldest is not None:
            until.append(oldest + window)
    if not until:
        return None
    return Lockout(retry_after_minutes=max(1, ceil((max(until) - now).total_seconds() / 60)))


def record_failure(db: AsyncSession, email: str, ip: str | None) -> None:
    db.add(LoginFailure(email=email, ip=ip))


async def clear(db: AsyncSession, email: str, settings: dict) -> None:
    """A successful login: the email's failures stop counting, and rows
    older than the window are no longer needed by anyone."""
    since = datetime.now(UTC) - timedelta(minutes=settings["window_minutes"])
    await db.execute(delete(LoginFailure).where(LoginFailure.email == email))
    await db.execute(delete(LoginFailure).where(LoginFailure.created_at <= since))
