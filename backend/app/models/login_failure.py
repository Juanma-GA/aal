from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LoginFailure(Base):
    """A failed login, counted per email and per address over a window
    (app/services/login_limit.py). In the database, not in memory, so the
    limit holds across restarts and several server processes."""

    __tablename__ = "login_failure"
    __table_args__ = (
        Index("ix_login_failure_email_created_at", "email", "created_at"),
        Index("ix_login_failure_ip_created_at", "ip", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    ip: Mapped[str | None] = mapped_column(INET, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
