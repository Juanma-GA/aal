"""Every ORM model, imported here so Base.metadata knows all tables
(alembic/env.py imports this package)."""

from app.models.app_parameter import AppParameter
from app.models.audit_log import AuditLog

__all__ = ["AppParameter", "AuditLog"]
