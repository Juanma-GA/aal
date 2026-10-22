"""Every ORM model, imported here so Base.metadata knows all tables
(alembic/env.py imports this package)."""

from app.models.app_parameter import AppParameter
from app.models.audit_log import AuditLog
from app.models.login_failure import LoginFailure
from app.models.material import Material
from app.models.refresh_token import RefreshToken
from app.models.role import Permission, Role, RolePermission, UserMaterialRole
from app.models.user import User

__all__ = [
    "AppParameter",
    "AuditLog",
    "LoginFailure",
    "Material",
    "Permission",
    "RefreshToken",
    "Role",
    "RolePermission",
    "User",
    "UserMaterialRole",
]
