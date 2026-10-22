"""audit.record stages a row in the caller's transaction (D11)."""
import uuid

import pytest
from sqlalchemy import delete, select

from app.models import AuditLog
from app.services import audit


async def test_record_is_written_with_the_change(db):
    user_id, material_id, entity_id = uuid.uuid4(), uuid.uuid4(), f"test-{uuid.uuid4()}"
    row = audit.record(
        db,
        action="app_parameter.updated",
        entity_type="app_parameter",
        entity_id=entity_id,
        user_id=user_id,
        material_id=material_id,
        before={"a": {"b": 1}},
        after={"a": {"b": 2}, "nombre": "Ñ"},
        ip="192.0.2.10",
    )
    await db.commit()
    try:
        stored = (await db.execute(select(AuditLog).where(AuditLog.entity_id == entity_id))).scalar_one()
        assert stored.id == row.id
        assert stored.created_at is not None
        assert (stored.user_id, stored.material_id) == (user_id, material_id)
        assert stored.action == "app_parameter.updated"
        assert stored.before == {"a": {"b": 1}}
        assert stored.after == {"a": {"b": 2}, "nombre": "Ñ"}
        assert str(stored.ip) == "192.0.2.10"
    finally:
        await db.execute(delete(AuditLog).where(AuditLog.entity_id == entity_id))
        await db.commit()


async def test_system_action_without_user_or_material(db):
    entity_id = f"test-{uuid.uuid4()}"
    audit.record(db, action="system.started", entity_type="system", entity_id=entity_id)
    await db.commit()
    try:
        stored = (await db.execute(select(AuditLog).where(AuditLog.entity_id == entity_id))).scalar_one()
        assert stored.user_id is None and stored.material_id is None and stored.ip is None
    finally:
        await db.execute(delete(AuditLog).where(AuditLog.entity_id == entity_id))
        await db.commit()


async def test_a_rolled_back_change_leaves_no_record(db):
    entity_id = f"test-{uuid.uuid4()}"
    audit.record(db, action="x.updated", entity_type="x", entity_id=entity_id)
    await db.rollback()
    assert (await db.execute(select(AuditLog).where(AuditLog.entity_id == entity_id))).first() is None


@pytest.mark.parametrize("field", ["action", "entity_type", "entity_id"])
async def test_empty_fields_are_refused(db, field):
    args = {"action": "x.updated", "entity_type": "x", "entity_id": "1", field: "  "}
    with pytest.raises(ValueError, match=field):
        audit.record(db, **args)
