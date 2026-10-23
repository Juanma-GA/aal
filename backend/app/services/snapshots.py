"""What the audit log keeps of each entity (D11): plain JSON, never a
password, a hash or a token (tests/security/test_no_secrets.py)."""

from fastapi import Request

from app.models import Material, User


def user_snapshot(user: User) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "is_admin": user.is_admin,
        "is_active": user.is_active,
        "must_change_password": user.must_change_password,
        "deleted": user.deleted_at is not None,
    }


def material_snapshot(material: Material) -> dict:
    return {
        "id": str(material.id),
        "noc": material.noc,
        "name": material.name,
        "part_number": material.part_number,
        "ncage": material.ncage,
        "description": material.description,
        "grupo_clase": material.grupo_clase,
        "catalog_version_id": str(material.catalog_version_id) if material.catalog_version_id else None,
        "copied_from_material_id": str(material.copied_from_material_id) if material.copied_from_material_id else None,
        "deleted": material.deleted_at is not None,
    }


def client_ip(request: Request) -> str | None:
    """The client address (behind nginx, uvicorn's --proxy-headers puts the
    real one here)."""
    return request.client.host if request.client else None
