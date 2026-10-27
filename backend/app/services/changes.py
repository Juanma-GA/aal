"""Change control of a CUF's CONFUNFIS (E17): one guard, on every flush.

A record of a CUF's CONFUNFIS -- a row, a functional product, an extra
function, an incompatibility -- is created, changed or removed: before the
session writes it (SQLAlchemy `before_flush`), the CUF's baselines decide:

- a baseline "en revisión": the CONFUNFIS is read-only (409
  `baseline_in_review`): the reviewer sees exactly what they approve;
- a reviewed baseline: the change needs an approved authorization of this
  CUF (409 `authorization_required`, or `authorization_not_usable`), named
  by the request (header X-Change-Authorization, bound in
  app/api/deps.current_user); each record touched is linked to it
  (authorization_change) and every audit row of the request carries it;
- no baseline: free, as before E17.

So every route, the book import, the copy towards a CUF and any script go
through the same rule, without a check in each of them. Parts and articles
are global: they are never blocked (their changes show in the diff against
a baseline). The findings kept on the records (refresh_observations) are
written as SQL, not through the session: they are computed, not a change.

`unguarded()` lifts the guard for maintenance scripts that put the database
back as it was (purge_verify_data.py --restore-confunfis, seed resets).
"""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import event, inspect, select
from sqlalchemy.orm import Session

from app.models import AuthorizationChange, Baseline, ChangeAuthorization, ExtraFunction, FunctionalProduct, Incompatibility, PhysicalPosition

GUARDED: dict[type, str] = {
    PhysicalPosition: "physical_position",
    FunctionalProduct: "functional_product",
    ExtraFunction: "extra_function",
    Incompatibility: "incompatibility",
}
HEADER = "X-Change-Authorization"


@dataclass
class _Request:
    user_id: uuid.UUID | None = None
    # What the request named (the header, as sent: checked by the guard).
    authorization: str | None = None
    # The authorizations the guard used in this request, by id (for the audit rows).
    used: dict[uuid.UUID, str] = field(default_factory=dict)


_REQUEST: ContextVar[_Request | None] = ContextVar("change_request", default=None)
_UNGUARDED: ContextVar[bool] = ContextVar("change_unguarded", default=False)


class ChangeBlocked(Exception):
    """A change the CUF's baselines do not allow: answered as a 409 (app/main.py)."""

    def __init__(self, error: str, /, **params: Any):
        super().__init__(error)
        self.code, self.params = error, params


def bind(user_id: uuid.UUID | None, authorization: str | None) -> None:
    """The request's user and the authorization it names (deps.current_user)."""
    _REQUEST.set(_Request(user_id=user_id, authorization=(authorization or "").strip() or None))


@contextmanager
def acting(user_id: uuid.UUID | None, authorization: uuid.UUID | None = None) -> Iterator[None]:
    """Outside a request (a script, a test): who changes, under which authorization."""
    token = _REQUEST.set(_Request(user_id=user_id, authorization=str(authorization) if authorization else None))
    try:
        yield
    finally:
        _REQUEST.reset(token)


@contextmanager
def unguarded() -> Iterator[None]:
    token = _UNGUARDED.set(True)
    try:
        yield
    finally:
        _UNGUARDED.reset(token)


def requested_authorization() -> uuid.UUID | None:
    """The authorization the current request names (None: none, or not an id)."""
    request = _REQUEST.get()
    return _parse(request.authorization) if request else None


def audit_note() -> dict[str, Any] | None:
    """What audit.record adds to the rows of a request that used an authorization."""
    request = _REQUEST.get()
    if request is None or not request.used:
        return None
    return {"change_authorization": [{"id": str(i), "code": c} for i, c in request.used.items()]}


def _action(obj: Any, deleted: bool) -> str | None:
    state = inspect(obj)
    if state.pending:
        return "creado"
    if deleted:
        return "eliminado"
    history = state.attrs.deleted_at.history if hasattr(obj, "deleted_at") else None
    if history is not None and history.added and history.added[0] is not None:
        return "eliminado"
    changed = [a.key for a in state.attrs if a.history.has_changes() and a.key not in ("updated_at", "updated_by", "version")]
    return "modificado" if changed else None


def _touched(session: Session) -> list[tuple[Any, str]]:
    out: list[tuple[Any, str]] = []
    for obj in list(session.new) + list(session.dirty):
        if type(obj) in GUARDED:
            action = _action(obj, False)
            if action:
                out.append((obj, action))
    for obj in session.deleted:
        if type(obj) in GUARDED:
            out.append((obj, "eliminado"))
    return out


def _parse(value: str | None) -> uuid.UUID | None:
    try:
        return uuid.UUID(value) if value else None
    except ValueError:
        return None


@event.listens_for(Session, "before_flush")
def _guard(session: Session, _context: Any, _instances: Any) -> None:
    if _UNGUARDED.get():
        return
    touched = _touched(session)
    if not touched:
        return
    by_material: dict[uuid.UUID, list[tuple[Any, str]]] = {}
    for obj, action in touched:
        by_material.setdefault(obj.material_id, []).append((obj, action))
    request = _REQUEST.get() or _Request()
    with session.no_autoflush:
        states: dict[uuid.UUID, set[str]] = {}
        for material_id, state in session.execute(
            select(Baseline.material_id, Baseline.state).where(
                Baseline.material_id.in_(by_material), Baseline.scope == "confunfis", Baseline.state.in_(("en_revision", "revisada"))
            )
        ).all():
            states.setdefault(material_id, set()).add(state)
        for material_id, items in by_material.items():
            need = required(states.get(material_id, set()))
            if need == "locked":
                raise ChangeBlocked("baseline_in_review")
            if need is None:
                continue
            wanted = _parse(request.authorization)
            if wanted is None:
                raise ChangeBlocked("authorization_required")
            authorization = session.get(ChangeAuthorization, wanted)
            if authorization is None or authorization.material_id != material_id or authorization.state != "aprobada":
                raise ChangeBlocked("authorization_not_usable", authorization=authorization.code if authorization else "")
            request.used[authorization.id] = authorization.code
            for obj, action in items:
                session.add(AuthorizationChange(
                    id=uuid.uuid4(), authorization_id=authorization.id, material_id=material_id, entity_type=GUARDED[type(obj)],
                    entity_id=str(obj.id), action=action, user_id=request.user_id,
                ))


def required(states: set[str]) -> str | None:
    """What a CUF in these baseline states needs to change its CONFUNFIS:
    None (free), "locked" (one in review) or "authorization"."""
    if "en_revision" in states:
        return "locked"
    if "revisada" in states:
        return "authorization"
    return None
