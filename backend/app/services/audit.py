"""Audit log of every mutation (D11, AACF G7).

record() stages one audit_log row in the caller's session and never
commits: the row goes into the same transaction as the change it
describes. If the row cannot be written, the commit fails and the change is
undone with it -- a mutation is never saved without its record.

`before` / `after` hold the entity's data as JSON-able values. Never a
password, a token or a secret.
"""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog


def record(
    db: AsyncSession,
    *,
    action: str,
    entity_type: str,
    entity_id: str,
    user_id: uuid.UUID | None = None,
    material_id: uuid.UUID | None = None,
    before: Any | None = None,
    after: Any | None = None,
    ip: str | None = None,
) -> AuditLog:
    """Stage one audit row (db.add, no commit); the caller commits it with
    the change.

    Args:
        db: The session the change itself is made in.
        action: What was done, as "<entity>.<verb>" (e.g. "app_parameter.updated").
        entity_type: The kind of entity changed (e.g. "app_parameter").
        entity_id: Its id or key.
        user_id: Who did it; None for the system itself.
        material_id: The material (CUF) it belongs to, when it belongs to one.
        before: The entity before the change (None when created).
        after: The entity after the change (None when deleted).
        ip: The client address of the request.

    Returns:
        The staged row.

    Raises:
        ValueError: An empty action, entity type or entity id.
    """
    for name, value in (("action", action), ("entity_type", entity_type), ("entity_id", entity_id)):
        if not value or not value.strip():
            raise ValueError(f"audit.record needs a non-empty {name}")
    row = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        material_id=material_id,
        before=before,
        after=after,
        ip=ip,
    )
    db.add(row)
    return row
