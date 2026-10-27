"""The whole role x permission x material matrix (D5), checked through
require_material_permission on every permission, plus the real material
routes: a user never sees a material they are not in."""

import pytest
import pytest_asyncio
from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.api.deps import require_material_permission
from app.db.base import async_session_factory
from app.main import app
from app.models import Permission, RolePermission
from helpers import bearer, login

# The seed matrix of encargo E01 §2.2, written out by hand on purpose: the
# test checks the database against the spec, not against itself.
VIEW = ["material.ver", "catalogo.ver", "confunfis.ver", "articulos.ver", "candidatos.ver", "tareas.ver", "validacion.ver"]
EDIT = ["material.editar", "confunfis.editar", "articulos.editar", "candidatos.editar", "tareas.editar"]
# E17 (migration 0018): the delivery, the baselines and the change authorizations.
E17_ANALYST = ["confunfis.entregar", "baseline.crear", "autorizacion.solicitar"]
E17_REVIEWER = ["confunfis.entregar", "baseline.revisar", "autorizacion.aprobar"]
EXPECTED = {
    "analista": set(VIEW + EDIT + ["revision.enviar", "validacion.ejecutar", "exportar"] + E17_ANALYST),
    "revisor": set(VIEW + ["revision.aprobar", "validacion.ejecutar", "exportar"] + E17_REVIEWER),
    "observador": set(VIEW + ["exportar"]),
}
ALL = sorted(set(VIEW + EDIT + ["revision.enviar", "revision.aprobar", "validacion.ejecutar", "exportar"] + E17_ANALYST + E17_REVIEWER))

_probe = APIRouter(prefix="/api/_test/permission")
for _code in ALL:

    async def _probe_route(access=Depends(require_material_permission(_code)), code=_code):
        return {"permission": code, "role": access.role}

    _probe.add_api_route(f"/{_code}/{{material_id}}", _probe_route, methods=["GET"])


@pytest.fixture(scope="module", autouse=True)
def _probe_routes():
    before = list(app.router.routes)
    app.include_router(_probe)
    yield
    app.router.routes[:] = before


async def test_the_seeded_matrix_is_the_spec():
    async with async_session_factory() as session:
        permissions = set((await session.execute(select(Permission.code))).scalars().all())
        rows = (await session.execute(select(RolePermission.role_code, RolePermission.permission_code))).all()
    assert permissions == set(ALL)
    seeded: dict[str, set] = {}
    for role, code in rows:
        seeded.setdefault(role, set()).add(code)
    assert seeded == EXPECTED


@pytest_asyncio.fixture
async def world(factory):
    material_a = await factory.material("Material A")
    material_b = await factory.material("Material B")
    users = {}
    for role in EXPECTED:
        users[role] = await factory.user()
        await factory.assign(users[role], material_a, role)
    users["admin"] = await factory.user(is_admin=True)
    users["nadie"] = await factory.user()
    return material_a, material_b, users


@pytest.mark.parametrize("role", ["analista", "revisor", "observador"])
async def test_each_role_on_its_material(client, world, role):
    material_a, _material_b, users = world
    token, _ = await login(client, users[role])
    for code in ALL:
        res = await client.get(f"/api/_test/permission/{code}/{material_a.id}", headers=bearer(token))
        if code in EXPECTED[role]:
            assert res.status_code == 200, (role, code, res.text)
        else:
            assert res.status_code == 403, (role, code, res.text)
            assert res.json()["detail"] == {"code": "permission_denied", "permission": code}


@pytest.mark.parametrize("role", ["analista", "revisor", "observador", "nadie"])
async def test_nobody_reaches_a_material_they_are_not_in(client, world, role):
    _material_a, material_b, users = world
    token, _ = await login(client, users[role])
    for code in ALL:
        res = await client.get(f"/api/_test/permission/{code}/{material_b.id}", headers=bearer(token))
        assert res.status_code == 404, (role, code)
        assert res.json()["detail"]["code"] == "material_not_found"
    assert (await client.get(f"/api/materials/{material_b.id}", headers=bearer(token))).status_code == 404
    listed = [m["id"] for m in (await client.get("/api/materials", headers=bearer(token))).json()]
    assert str(material_b.id) not in listed


async def test_the_admin_can_do_everything_everywhere(client, world):
    material_a, material_b, users = world
    token, _ = await login(client, users["admin"])
    for material in (material_a, material_b):
        for code in ALL:
            res = await client.get(f"/api/_test/permission/{code}/{material.id}", headers=bearer(token))
            assert res.status_code == 200, code
    listed = {m["id"] for m in (await client.get("/api/materials", headers=bearer(token))).json()}
    assert {str(material_a.id), str(material_b.id)} <= listed


async def test_the_list_carries_role_and_permissions(client, world):
    material_a, _material_b, users = world
    token, _ = await login(client, users["observador"])
    (item,) = (await client.get("/api/materials", headers=bearer(token))).json()
    assert item["id"] == str(material_a.id)
    assert item["role"] == "observador"
    assert set(item["permissions"]) == EXPECTED["observador"]


async def test_only_the_admin_manages_materials_users_and_audit(client, world):
    material_a, _material_b, users = world
    for role in ("analista", "revisor", "observador"):
        token, _ = await login(client, users[role])
        h = bearer(token)
        calls = [
            await client.patch(f"/api/materials/{material_a.id}", json={"version": 1, "name": "x"}, headers=h),
            await client.post("/api/materials", json={"name": "x"}, headers=h),
            await client.delete(f"/api/materials/{material_a.id}?confirm=true", headers=h),
            await client.get("/api/users", headers=h),
            await client.get("/api/audit", headers=h),
            await client.get("/api/parameters", headers=h),
        ]
        for res in calls:
            assert res.status_code == 403, (role, res.request.url, res.text)
            assert res.json()["detail"]["code"] == "admin_required"


async def test_a_deleted_material_grants_nothing(client, world):
    material_a, _material_b, users = world
    admin_token, _ = await login(client, users["admin"])
    assert (await client.delete(f"/api/materials/{material_a.id}?confirm=true", headers=bearer(admin_token))).status_code == 204
    token, _ = await login(client, users["analista"])
    assert (await client.get(f"/api/materials/{material_a.id}", headers=bearer(token))).status_code == 404
    assert (await client.get("/api/materials", headers=bearer(token))).json() == []
