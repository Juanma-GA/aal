"""Every ORM model, imported here so Base.metadata knows all tables
(alembic/env.py imports this package)."""

from app.models.app_parameter import AppParameter
from app.models.article import FIELD_COLUMNS, MAX_LIFE_CONTROLS, NAME_ORIGINS, Article, ArticleLifeControl
from app.models.audit_log import AuditLog
from app.models.catalog import CatalogVersion, MaterialCategory, MaterialSubcategory, SnsExtraName, SnsPosition, SubcategorySns
from app.models.import_job import IMPORT_JOB_STATUSES, ImportJob
from app.models.login_failure import LoginFailure
from app.models.material import SNS_REQUEST_STATES, Material, MaterialSubcategoryLink, SnsRequest
from app.models.module import MODULE_STATUSES, ModuleCatalog, ModuleGroup, ModuleRequirement
from app.models.reference import (
    ATTRIBUTE_TYPES,
    REFERENCE_CODE_MAX_LENGTH,
    REFERENCE_DEFINITION_MAX_LENGTH,
    REFERENCE_DESCRIPTION_MAX_LENGTH,
    ArticleFieldDefinition,
    ReferenceTable,
    ReferenceValue,
)
from app.models.refresh_token import RefreshToken
from app.models.role import Permission, Role, RolePermission, UserMaterialRole
from app.models.user import User

__all__ = [
    "ATTRIBUTE_TYPES",
    "AppParameter",
    "Article",
    "ArticleLifeControl",
    "ArticleFieldDefinition",
    "AuditLog",
    "CatalogVersion",
    "FIELD_COLUMNS",
    "IMPORT_JOB_STATUSES",
    "ImportJob",
    "LoginFailure",
    "MAX_LIFE_CONTROLS",
    "MODULE_STATUSES",
    "Material",
    "NAME_ORIGINS",
    "MaterialCategory",
    "MaterialSubcategory",
    "MaterialSubcategoryLink",
    "ModuleCatalog",
    "ModuleGroup",
    "ModuleRequirement",
    "Permission",
    "REFERENCE_CODE_MAX_LENGTH",
    "REFERENCE_DEFINITION_MAX_LENGTH",
    "REFERENCE_DESCRIPTION_MAX_LENGTH",
    "ReferenceTable",
    "ReferenceValue",
    "RefreshToken",
    "Role",
    "RolePermission",
    "SNS_REQUEST_STATES",
    "SnsExtraName",
    "SnsPosition",
    "SnsRequest",
    "SubcategorySns",
    "User",
    "UserMaterialRole",
]
