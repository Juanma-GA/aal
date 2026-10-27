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

E17b: the CUF's subcategories and catalog version (its allowed functions:
a change can leave the approved CONFUNFIS out of them, CF-001) go through
the same rule; its descriptive data does not.

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

from app.models import (
    AuditLog,
    AuthorizationChange,
    Baseline,
    ChangeAuthorization,
    ExtraFunction,
    FunctionalProduct,
    Incompatibility,
    Material,
    MaterialSubcategoryLink,
    PhysicalPosition,
)

GUARDED: dict[type, str] = {
    PhysicalPosition: "physical_position",
    FunctionalProduct: "functional_product",
    ExtraFunction: "extra_function",
    Incompatibility: "incompatibility",
}
# E17b: the CUF's own change-controlled data, its allowed functions: its subcategories (each link)
# and its catalog version. Its descriptive data (name, description, Grupo-Clase…) stays free.
MATERIAL_FIELDS = ("catalog_version_id",)
HEADER = "X-Change-Authorization"


@dataclass
class _Request:
    user_id: uuid.UUID | None = None
    # What the request named (the header, as sent: checked by the guard).
    authorization: str | None = None
    # The authorizations the guard used in this request, by id (for the audit rows).
    used: dict[uuid.UUID, str] = field(default_factory=dict)
    # What the request already linked to an authorization (one row each, across its flushes).
    linked: set[tuple[uuid.UUID, str, str]] = field(default_factory=set)


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


def _material_change(obj: Any) -> bool:
    """A CUF whose catalog version changes (a new one has no baseline: never guarded)."""
    state = inspect(obj)
    return not state.pending and any(state.attrs[name].history.has_changes() for name in MATERIAL_FIELDS)


def _touched(session: Session) -> list[tuple[Any, str]]:
    out: list[tuple[Any, str]] = []
    for obj in list(session.new) + list(session.dirty):
        if type(obj) in GUARDED:
            action = _action(obj, False)
            if action:
                out.append((obj, action))
        elif isinstance(obj, MaterialSubcategoryLink) or (isinstance(obj, Material) and _material_change(obj)):
            out.append((obj, "modificado"))
    for obj in session.deleted:
        if type(obj) in GUARDED:
            out.append((obj, "eliminado"))
        elif isinstance(obj, MaterialSubcategoryLink):
            out.append((obj, "modificado"))
    return out


def _material_of(obj: Any) -> uuid.UUID:
    return obj.id if isinstance(obj, Material) else obj.material_id


def _entity(obj: Any) -> tuple[str, str]:
    """What authorization_change names: the record, or (its subcategories, its catalog version) the CUF itself."""
    if isinstance(obj, (Material, MaterialSubcategoryLink)):
        return "material", str(_material_of(obj))
    return GUARDED[type(obj)], str(obj.id)


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
    if touched:
        _check(session, touched)
    _note_audit_rows(session)


def _note_audit_rows(session: Session) -> None:
    """Every audit row of the request names the authorizations it used, a removal's too
    (its row is staged before the flush that finds the authorization)."""
    note = audit_note()
    if note is None:
        return
    for obj in session.new:
        if isinstance(obj, AuditLog) and not (obj.after or {}).get("change_authorization"):
            obj.after = {**(obj.after or {}), **note}


def _check(session: Session, touched: list[tuple[Any, str]]) -> None:
    by_material: dict[uuid.UUID, list[tuple[Any, str]]] = {}
    for obj, action in touched:
        by_material.setdefault(_material_of(obj), []).append((obj, action))
    request = _REQUEST.get() or _Request()
    with session.no_autoflush:
        # FOR SHARE on the CUF: "Crear baseline" (FOR UPDATE on it) waits for this change to commit
        # and then finds its validation outdated, or this change waits and then finds the baseline.
        session.execute(select(Material.id).where(Material.id.in_(by_material)).with_for_update(read=True))
        states: dict[uuid.UUID, set[str]] = {}
        # FOR SHARE: a baseline being reviewed, withdrawn or an authorization being closed (FOR UPDATE)
        # waits for this change, or this change for it -- never a change under a state just left.
        for material_id, state in session.execute(
            select(Baseline.material_id, Baseline.state).where(
                Baseline.material_id.in_(by_material), Baseline.scope == "confunfis", Baseline.state.in_(("en_revision", "revisada"))
            ).with_for_update(read=True)
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
            authorization = session.get(ChangeAuthorization, wanted, with_for_update={"read": True})
            if authorization is None or authorization.material_id != material_id or authorization.state != "aprobada":
                # Another CUF's authorization is not named: its code carries that CUF's P/N.
                own = authorization is not None and authorization.material_id == material_id
                raise ChangeBlocked("authorization_not_usable", authorization=authorization.code if own else "")
            request.used[authorization.id] = authorization.code
            for obj, action in items:
                entity_type, entity_id = _entity(obj)
                if (authorization.id, entity_type, entity_id) in request.linked:
                    continue
                request.linked.add((authorization.id, entity_type, entity_id))
                session.add(AuthorizationChange(
                    id=uuid.uuid4(), authorization_id=authorization.id, material_id=material_id, entity_type=entity_type,
                    entity_id=entity_id, action=action, user_id=request.user_id,
                ))


def required(states: set[str]) -> str | None:
    """What a CUF in these baseline states needs to change its CONFUNFIS:
    None (free), "locked" (one in review) or "authorization"."""
    if "en_revision" in states:
        return "locked"
    if "revisada" in states:
        return "authorization"
    return None
