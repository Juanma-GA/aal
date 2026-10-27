"""Baselines and change authorizations of a CUF's CONFUNFIS (E17, S3000L
ch. 4). The rule that enforces them on every change is
app/services/changes.py; this module makes, reviews and compares them.

The snapshot is one JSON document per baseline (`baseline.snapshot`), not a
copy of every table: a baseline is read whole (to compare it, to deliver
it), never queried by field, and its shape must not follow the tables'
migrations -- v1 stays what it was the day it was frozen. It holds:

- `material`: the CUF's identity, catalog version and subcategories;
- `rows`, `products`, `extras`, `incompatibilities`: the records, by id;
- `articles`: a copy of every article the rows and their parts use (the 30
  SIGLE fields, references, life controls) and `parts`: their breakdowns --
  global data that changes afterwards;
- `book` and `fichero_carga`: the very sheets "Exportar para entrega"
  writes, so what is delivered is exactly what was approved.

Values that JSON has no type for go tagged ({"$d": "1.5"}: a Decimal), so
the delivery writes numbers as numbers. `snapshot_hash` (SHA-256) is taken
once; nothing writes a baseline's snapshot again.

States: en_revision -> revisada | rechazada | retirada. Four eyes: its
author never reviews it, admin or not; an authorization is never decided by
whoever asked for it.
"""

import hashlib
import json
import re
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.texts import text
from app.models import (
    Article,
    ArticlePart,
    AuthorizationChange,
    Baseline,
    ChangeAuthorization,
    ExtraFunction,
    FunctionalProduct,
    Incompatibility,
    Material,
    PhysicalPosition,
    User,
    ValidationRun,
)
from app.services import audit, confunfis, cuf, validation
from app.services import confunfis_extras as extras
from app.services.articles import data_of, life_of
from app.services.confunfis_graph import key_text
from app.services.reference import codes_by_state

SCOPE = "confunfis"
KIND_TABLE = "TIPO_AUTORIZACION"
FORMAT = 1


class BaselineError(Exception):
    """A step the state of the baseline (or authorization) does not allow: a 409 (403 for four eyes)."""

    def __init__(self, error: str, status: int = 409, /, **params: Any):
        super().__init__(error)
        self.code, self.status, self.params = error, status, params


# ── the JSON codec of a snapshot ─────────────────────────────────────────


def encode(value: Any) -> Any:
    if isinstance(value, Decimal):
        return {"$d": str(value)}
    if isinstance(value, datetime | date):
        return {"$t": value.isoformat()}
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, dict):
        return {k: encode(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [encode(v) for v in value]
    return value


def decode(value: Any) -> Any:
    if isinstance(value, dict):
        if set(value) == {"$d"}:
            return Decimal(value["$d"])
        if set(value) == {"$t"}:
            text = value["$t"]
            return datetime.fromisoformat(text) if "T" in text else date.fromisoformat(text)
        return {k: decode(v) for k, v in value.items()}
    if isinstance(value, list):
        return [decode(v) for v in value]
    return value


def digest(snapshot: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


# ── the snapshot ─────────────────────────────────────────────────────────

_ROW = ("sns", "co", "al", "qty", "cs_sns", "cs_co", "cs_al", "article_name", "function_text", "ct_sigle", "article_id", "article_reference_id")
_PRODUCT = ("designation", "pol_code", "nae", "noc", "supply_unit", "quantity", "unit")


def _pick(obj: Any, names: tuple[str, ...]) -> dict[str, Any]:
    return {n: encode(getattr(obj, n)) for n in names}


async def snapshot(db: AsyncSession, material: Material, *, book: bool = True) -> dict[str, Any]:
    """The CUF's CONFUNFIS now, as a baseline keeps it (`book`: with the delivery's sheets)."""
    from app.services import anexo_xi_export
    from app.services.article_import import FICHERO_CARGA, export_values

    rows = await confunfis.live_rows(db, material.id)
    products = await extras.live_products(db, material.id)
    extra_functions = await extras.live_extras(db, material.id)
    incompatibilities = await extras.live_incompatibilities(db, material.id)
    used = {r.article_id for r in rows if r.article_id}
    parts = [p for p in await extras.live_parts(db) if p.parent_article_id in used]
    ids = used | {p.part_article_id for p in parts if p.part_article_id}
    articles = list((await db.execute(select(Article).where(Article.id.in_(ids), Article.deleted_at.is_(None)).order_by(Article.nombre, Article.noc, Article.id))).scalars()) if ids else []
    doc: dict[str, Any] = {
        "format": FORMAT,
        "material": {
            "noc": material.noc, "name": material.name, "part_number": material.part_number, "ncage": material.ncage,
            "catalog_version_id": encode(material.catalog_version_id), "subcategories": sorted(await cuf.subcategory_codes(db, material.id)),
        },
        "rows": {str(r.id): _pick(r, _ROW) for r in rows},
        "products": {str(p.id): _pick(p, _PRODUCT) for p in products},
        "extras": {str(e.id): {"position_id": str(e.position_id), "sns": e.sns, "criterion": e.criterion, "comment": e.comment} for e in extra_functions},
        "incompatibilities": {
            str(i.id): {"row_a_id": str(i.row_a_id), "row_b_id": str(i.row_b_id), "kind": i.kind, "reason": i.reason} for i in incompatibilities
        },
        "articles": {
            str(a.id): {
                "noc": a.noc, "nombre": a.nombre, "data": encode(data_of(a)),
                "references": sorted(({"id": str(x.id), "pn": x.pn, "ncage": x.ncage, "principal": x.principal} for x in a.live_references), key=lambda x: (x["pn"] or "", x["ncage"] or "")),
                "life": [{"unit_code": c.unit_code, "quantity": encode(c.quantity)} for c in life_of(a)],
            }
            for a in articles
        },
        "parts": {
            str(p.id): {
                "parent_article_id": str(p.parent_article_id), "cop": p.cop, "alp": p.alp, "quantity": encode(p.quantity),
                "part_article_id": encode(p.part_article_id), "article_reference_id": encode(p.article_reference_id), "part_name": p.part_name,
            }
            for p in parts
        },
    }
    if book:
        doc["book"] = encode(await anexo_xi_export.anexo_rows(db, material, rows))
        doc["fichero_carga"] = [encode(export_values(a, FICHERO_CARGA)) for a in articles]
    return doc


# ── reading ──────────────────────────────────────────────────────────────


async def baselines_of(db: AsyncSession, material: Material) -> list[Baseline]:
    query = select(Baseline).where(Baseline.material_id == material.id, Baseline.scope == SCOPE).order_by(Baseline.number.desc())
    return list((await db.execute(query)).scalars())


async def latest_reviewed(db: AsyncSession, material: Material) -> Baseline | None:
    query = select(Baseline).where(Baseline.material_id == material.id, Baseline.scope == SCOPE, Baseline.state == "revisada")
    return (await db.execute(query.order_by(Baseline.number.desc()).limit(1))).scalar_one_or_none()


async def in_review(db: AsyncSession, material: Material) -> Baseline | None:
    query = select(Baseline).where(Baseline.material_id == material.id, Baseline.scope == SCOPE, Baseline.state == "en_revision")
    return (await db.execute(query)).scalar_one_or_none()


async def get(db: AsyncSession, material: Material, baseline_id: uuid.UUID, *, lock: bool = False) -> Baseline:
    query = select(Baseline).where(Baseline.id == baseline_id, Baseline.material_id == material.id)
    found = (await db.execute(query.with_for_update() if lock else query)).scalar_one_or_none()
    if found is None:
        raise BaselineError("baseline_not_found", 404)
    return found


async def authorizations_of(db: AsyncSession, material: Material) -> list[ChangeAuthorization]:
    query = select(ChangeAuthorization).where(ChangeAuthorization.material_id == material.id).order_by(ChangeAuthorization.number.desc())
    return list((await db.execute(query)).scalars())


async def state(db: AsyncSession, material: Material) -> dict[str, Any]:
    """The CUF's configuration state (the Panel, the CONFUNFIS band)."""
    reviewed = await latest_reviewed(db, material)
    review = await in_review(db, material)
    authorizations = await authorizations_of(db, material)
    changes = len(diff(reviewed.snapshot, await snapshot(db, material, book=False))) if reviewed else 0
    states = {b.state for b in (reviewed, review) if b is not None}
    return {
        "reviewed": reviewed, "in_review": review, "changes_since": changes,
        "open_authorizations": [a for a in authorizations if a.state in ("solicitada", "aprobada")],
        "usable_authorizations": [a for a in authorizations if a.state == "aprobada"],
        "edit": {"locked": "locked", "authorization": "authorization"}.get(_need(states)) or "free",
    }


def _need(states: set[str]) -> str | None:
    from app.services.changes import required

    return required(states)


# ── making and reviewing baselines ───────────────────────────────────────


async def create(db: AsyncSession, material: Material, user: User, ip: str | None) -> Baseline:
    """Freezes the CONFUNFIS: only with an up-to-date validation free of blocking findings, one in review at a time."""
    await db.execute(select(Material.id).where(Material.id == material.id).with_for_update())
    if await in_review(db, material) is not None:
        raise BaselineError("baseline_already_in_review")
    run = await validation.latest(db, material)
    problems: list[dict[str, Any]] = []
    if run is None:
        problems.append({"code": "delivery_not_validated", "params": {}})
    else:
        stale = await validation.outdated(db, material, run)
        if stale["data"] or stale["rules"]:
            problems.append({"code": "delivery_outdated", "params": {}})
        if run.blocking:
            problems.append({"code": "delivery_blocking", "params": {"count": run.blocking}})
    if problems:
        raise BaselineError("baseline_not_valid", problems=problems)
    number = ((await db.scalar(select(func.max(Baseline.number)).where(Baseline.material_id == material.id, Baseline.scope == SCOPE))) or 0) + 1
    doc = await snapshot(db, material)
    baseline = Baseline(
        id=uuid.uuid4(), material_id=material.id, scope=SCOPE, number=number, state="en_revision", created_by=user.id,
        validation_run_id=run.id, snapshot=doc, snapshot_hash=digest(doc), data_fingerprint=run.data_fingerprint, version=1,
    )
    db.add(baseline)
    await db.flush()
    audit.record(
        db, action="baseline.created", entity_type="baseline", entity_id=str(baseline.id), user_id=user.id, material_id=material.id,
        after={"number": number, "run": str(run.id), "rows": len(doc["rows"]), "snapshot_hash": baseline.snapshot_hash}, ip=ip,
    )
    return baseline


def _check_version(baseline: Baseline | ChangeAuthorization, version: int) -> None:
    if baseline.version != version:
        raise BaselineError("version_conflict", current=baseline.version)


async def withdraw(db: AsyncSession, material: Material, baseline: Baseline, version: int, user: User, ip: str | None) -> Baseline:
    _check_version(baseline, version)
    if baseline.state != "en_revision":
        raise BaselineError("baseline_state_invalid", state=baseline.state)
    if baseline.created_by != user.id and not user.is_admin:
        raise BaselineError("baseline_withdraw_not_author", 403)
    baseline.state, baseline.version = "retirada", baseline.version + 1
    audit.record(db, action="baseline.withdrawn", entity_type="baseline", entity_id=str(baseline.id), user_id=user.id, material_id=material.id,
                 after={"number": baseline.number}, ip=ip)
    return baseline


async def review(db: AsyncSession, material: Material, baseline: Baseline, version: int, user: User, approve: bool, comment: str | None, ip: str | None) -> Baseline:
    _check_version(baseline, version)
    if baseline.state != "en_revision":
        raise BaselineError("baseline_state_invalid", state=baseline.state)
    # Four eyes: never its author, admin or not.
    if baseline.created_by == user.id:
        raise BaselineError("baseline_review_own", 403)
    comment = (comment or "").strip() or None
    if not approve and not comment:
        raise BaselineError("baseline_reject_needs_comment", 422)
    now = datetime.now(UTC)
    baseline.state = "revisada" if approve else "rechazada"
    baseline.reviewed_by, baseline.reviewed_at, baseline.review_comment, baseline.version = user.id, now, comment, baseline.version + 1
    closed: list[str] = []
    if approve:
        # The approved authorizations it includes (changes made before it was frozen) are closed.
        included = select(AuthorizationChange.authorization_id).where(
            AuthorizationChange.material_id == material.id, AuthorizationChange.created_at <= baseline.created_at
        )
        for a in (await db.execute(select(ChangeAuthorization).where(
            ChangeAuthorization.material_id == material.id, ChangeAuthorization.state == "aprobada", ChangeAuthorization.id.in_(included)
        ).with_for_update())).scalars():
            a.state, a.closed_at, a.closed_by, a.closed_in_baseline_id, a.version = "cerrada", now, user.id, baseline.id, a.version + 1
            closed.append(a.code)
            audit.record(db, action="authorization.closed", entity_type="change_authorization", entity_id=str(a.id), user_id=user.id,
                         material_id=material.id, after={"code": a.code, "baseline": baseline.number}, ip=ip)
    audit.record(
        db, action="baseline.approved" if approve else "baseline.rejected", entity_type="baseline", entity_id=str(baseline.id), user_id=user.id,
        material_id=material.id, after={"number": baseline.number, "comment": comment, "closed_authorizations": closed}, ip=ip,
    )
    return baseline


async def retained_runs(db: AsyncSession, material: Material) -> set[uuid.UUID]:
    """validation.RETAINED_RUNS: a baseline's validation is never purged."""
    query = select(Baseline.validation_run_id).where(Baseline.material_id == material.id, Baseline.validation_run_id.is_not(None))
    return set((await db.execute(query)).scalars())


validation.RETAINED_RUNS.append(retained_runs)


# ── change authorizations ────────────────────────────────────────────────


def cuf_code(material: Material) -> str:
    """The <CUF> of AC-<CUF>-NNN: its P/N (TRM-4X4-A), else its name's initials."""
    if material.part_number:
        return re.sub(r"[^A-Z0-9-]+", "", material.part_number.upper())[:30] or "CUF"
    initials = "".join(w[0] for w in re.findall(r"[A-Za-z0-9]+", material.name.upper()))
    return initials[:8] or "CUF"


async def request_authorization(
    db: AsyncSession, material: Material, kind: str, description: str, reason: str, user: User, ip: str | None,
) -> ChangeAuthorization:
    kinds = await codes_by_state(db, KIND_TABLE)
    if not kinds.get(kind):
        raise BaselineError("authorization_kind_invalid", 422)
    await db.execute(select(Material.id).where(Material.id == material.id).with_for_update())
    number = ((await db.scalar(select(func.max(ChangeAuthorization.number)).where(ChangeAuthorization.material_id == material.id))) or 0) + 1
    item = ChangeAuthorization(
        id=uuid.uuid4(), material_id=material.id, number=number, code=f"AC-{cuf_code(material)}-{number:03d}", kind=kind,
        description=description.strip(), reason=reason.strip(), state="solicitada", requested_by=user.id, version=1,
    )
    db.add(item)
    await db.flush()
    audit.record(db, action="authorization.requested", entity_type="change_authorization", entity_id=str(item.id), user_id=user.id,
                 material_id=material.id, after={"code": item.code, "kind": kind, "description": item.description, "reason": item.reason}, ip=ip)
    return item


async def get_authorization(db: AsyncSession, material: Material, authorization_id: uuid.UUID) -> ChangeAuthorization:
    query = select(ChangeAuthorization).where(ChangeAuthorization.id == authorization_id, ChangeAuthorization.material_id == material.id)
    found = (await db.execute(query.with_for_update())).scalar_one_or_none()
    if found is None:
        raise BaselineError("authorization_not_found", 404)
    return found


async def decide_authorization(
    db: AsyncSession, material: Material, item: ChangeAuthorization, version: int, user: User, approve: bool, comment: str | None, ip: str | None,
) -> ChangeAuthorization:
    _check_version(item, version)
    if item.state != "solicitada":
        raise BaselineError("authorization_state_invalid", state=item.state)
    if item.requested_by == user.id:
        raise BaselineError("authorization_decide_own", 403)
    comment = (comment or "").strip() or None
    if not approve and not comment:
        raise BaselineError("authorization_reject_needs_comment", 422)
    item.state = "aprobada" if approve else "rechazada"
    item.decided_by, item.decided_at, item.decision_comment, item.version = user.id, datetime.now(UTC), comment, item.version + 1
    audit.record(db, action="authorization.approved" if approve else "authorization.rejected", entity_type="change_authorization",
                 entity_id=str(item.id), user_id=user.id, material_id=material.id, after={"code": item.code, "comment": comment}, ip=ip)
    return item


async def close_authorization(db: AsyncSession, material: Material, item: ChangeAuthorization, version: int, user: User, ip: str | None) -> ChangeAuthorization:
    _check_version(item, version)
    if item.state not in ("solicitada", "aprobada"):
        raise BaselineError("authorization_state_invalid", state=item.state)
    if item.requested_by != user.id and not user.is_admin:
        raise BaselineError("authorization_close_not_requester", 403)
    item.state, item.closed_at, item.closed_by, item.version = "cerrada", datetime.now(UTC), user.id, item.version + 1
    audit.record(db, action="authorization.closed", entity_type="change_authorization", entity_id=str(item.id), user_id=user.id,
                 material_id=material.id, after={"code": item.code}, ip=ip)
    return item


async def changes_of(db: AsyncSession, authorization: ChangeAuthorization) -> list[AuthorizationChange]:
    query = select(AuthorizationChange).where(AuthorizationChange.authorization_id == authorization.id).order_by(AuthorizationChange.created_at)
    return list((await db.execute(query)).scalars())


async def labels_of(db: AsyncSession, changes: list[AuthorizationChange], current: dict[str, Any]) -> dict[str, str]:
    """A readable name for each record an authorization touched: as it is now, or (removed) as a baseline kept it."""
    sections = {"physical_position": ("row", "rows"), "functional_product": ("product", "products"), "extra_function": ("extra", "extras"), "incompatibility": ("incompatibility", "incompatibilities")}
    docs: list[dict[str, Any]] | None = None
    out: dict[str, str] = {}
    for c in changes:
        if c.entity_type == "material":
            out[c.entity_id] = text("baselines.materialChange", name=current.get("material", {}).get("name") or "")
            continue
        entity, section = sections.get(c.entity_type, (None, None))
        if entity is None:
            continue
        doc = current if c.entity_id in current.get(section, {}) else None
        if doc is None:
            if docs is None:
                docs = [b.snapshot for b in (await db.execute(select(Baseline).where(Baseline.material_id == c.material_id).order_by(Baseline.number.desc()))).scalars()]
            doc = next((d for d in docs if c.entity_id in d.get(section, {})), None)
        if doc is not None:
            out[c.entity_id] = _label(entity, doc, c.entity_id, doc[section][c.entity_id])
    return out


# ── the diff ─────────────────────────────────────────────────────────────


def _shown(value: Any) -> str:
    value = decode(value)
    if value is None or value == "":
        return ""
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    return str(value)


def _row_label(doc: dict[str, Any], row_id: str | None) -> str:
    r = doc.get("rows", {}).get(row_id or "")
    return f"{key_text((r['sns'], r['co'], r['al']))} · {r.get('article_name') or ''}".rstrip(" ·") if r else (row_id or "")


def _identity(doc: dict[str, Any], article_id: str | None, reference_id: str | None) -> dict[str, str]:
    a = doc.get("articles", {}).get(article_id or "")
    if a is None:
        return {"noc": "", "pn": "", "ncage": ""}
    ref = next((x for x in a["references"] if x["id"] == reference_id), None)
    return {"noc": a.get("noc") or "", "pn": (ref or {}).get("pn") or "", "ncage": (ref or {}).get("ncage") or ""}


def _flat(entity: str, doc: dict[str, Any], key: str, item: dict[str, Any]) -> dict[str, str]:
    """An entity's fields, as the diff compares and shows them."""
    if entity == "row":
        fields = {n: _shown(item[n]) for n in _ROW if n not in ("article_id", "article_reference_id")}
        return {**fields, **_identity(doc, item.get("article_id"), item.get("article_reference_id"))}
    if entity == "product":
        return {n: _shown(item[n]) for n in _PRODUCT}
    if entity == "extra":
        return {"row": _row_label(doc, item["position_id"]), "sns": item["sns"], "criterion": item["criterion"], "comment": item.get("comment") or ""}
    if entity == "incompatibility":
        return {"row_a": _row_label(doc, item["row_a_id"]), "kind": item["kind"], "row_b": _row_label(doc, item["row_b_id"]), "reason": item.get("reason") or ""}
    if entity == "article":
        fields = {f"data.{k}": _shown(v) for k, v in item["data"].items()}
        fields["references"] = ", ".join(f"{x['pn']}/{x['ncage'] or ''}{' *' if x['principal'] else ''}" for x in item["references"])
        fields["life"] = ", ".join(f"{c['unit_code'] or ''} {_shown(c['quantity'])}".strip() for c in item["life"])
        return {"nombre": item.get("nombre") or "", "noc": item.get("noc") or "", **fields}
    if entity == "part":
        parent = doc.get("articles", {}).get(item["parent_article_id"], {})
        ident = _identity(doc, item.get("part_article_id"), item.get("article_reference_id"))
        return {"parent": parent.get("nombre") or "", "cop": item["cop"], "alp": item["alp"], "quantity": _shown(item["quantity"]), **ident, "part_name": item.get("part_name") or ""}
    raise ValueError(entity)


def _label(entity: str, doc: dict[str, Any], key: str, item: dict[str, Any]) -> str:
    if entity == "row":
        return _row_label(doc, key)
    if entity == "product":
        return f"{item.get('pol_code') or '—'} · {item.get('designation') or ''}"
    if entity == "extra":
        return f"{_row_label(doc, item['position_id'])} + {item['sns']}"
    if entity == "incompatibility":
        return f"{_row_label(doc, item['row_a_id'])} {item['kind']} {_row_label(doc, item['row_b_id'])}"
    if entity == "article":
        return f"{item.get('noc') or ''} · {item.get('nombre') or ''}".strip(" ·")
    if entity == "part":
        parent = doc.get("articles", {}).get(item["parent_article_id"], {})
        return f"{parent.get('nombre') or ''} · {item['cop']}/{item['alp']}"
    return key


_ENTITIES = (("row", "rows"), ("product", "products"), ("extra", "extras"), ("incompatibility", "incompatibilities"), ("article", "articles"), ("part", "parts"))


def diff(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
    """What changed from one snapshot to the other, by entity and field."""
    out: list[dict[str, Any]] = []
    for entity, section in _ENTITIES:
        old, new = before.get(section, {}), after.get(section, {})
        for key in sorted(set(old) | set(new), key=lambda k: _label(entity, after if k in new else before, k, (new.get(k) or old.get(k)))):
            if key not in old:
                out.append({"entity": entity, "id": key, "label": _label(entity, after, key, new[key]), "change": "added",
                            "fields": [{"field": f, "before": "", "after": v} for f, v in _flat(entity, after, key, new[key]).items() if v]})
            elif key not in new:
                out.append({"entity": entity, "id": key, "label": _label(entity, before, key, old[key]), "change": "removed",
                            "fields": [{"field": f, "before": v, "after": ""} for f, v in _flat(entity, before, key, old[key]).items() if v]})
            else:
                a, b = _flat(entity, before, key, old[key]), _flat(entity, after, key, new[key])
                fields = [{"field": f, "before": a.get(f, ""), "after": b.get(f, "")} for f in sorted(set(a) | set(b), key=list({**a, **b}).index) if a.get(f, "") != b.get(f, "")]
                if fields:
                    out.append({"entity": entity, "id": key, "label": _label(entity, after, key, new[key]), "change": "modified", "fields": fields})
    # The CUF itself: its subcategories and catalog version are change-controlled (E17b, changes.py), its
    # identity is not; a change to any of them shows here.
    a, b = _material_fields(before.get("material", {})), _material_fields(after.get("material", {}))
    fields = [{"field": f, "before": a[f], "after": b[f]} for f in a if a[f] != b[f]]
    if fields:
        out.append({"entity": "material", "id": "material", "label": after.get("material", {}).get("name") or "", "change": "modified", "fields": fields})
    return out


def _material_fields(m: dict[str, Any]) -> dict[str, str]:
    return {
        "name": m.get("name") or "", "noc": m.get("noc") or "", "part_number": m.get("part_number") or "", "ncage": m.get("ncage") or "",
        "subcategories": ", ".join(m.get("subcategories") or []), "catalog_version_id": _shown(decode(m.get("catalog_version_id"))) if m.get("catalog_version_id") else "",
    }


async def with_authorizations(db: AsyncSession, material: Material, entries: list[dict[str, Any]], since: datetime, until: datetime | None) -> list[dict[str, Any]]:
    """Each change of the diff with the authorizations that backed it (between the two snapshots)."""
    query = (
        select(AuthorizationChange.entity_id, ChangeAuthorization.id, ChangeAuthorization.code)
        .join(ChangeAuthorization, ChangeAuthorization.id == AuthorizationChange.authorization_id)
        .where(AuthorizationChange.material_id == material.id, AuthorizationChange.created_at > since)
    )
    if until is not None:
        query = query.where(AuthorizationChange.created_at <= until)
    by_entity: dict[str, dict[str, str]] = {}
    for entity_id, aid, code in (await db.execute(query)).all():
        by_entity.setdefault(entity_id, {})[str(aid)] = code
    # The CUF's own changes (subcategories, catalog version) are named by its id (changes._entity).
    key = lambda e: str(material.id) if e["entity"] == "material" else e["id"]  # noqa: E731
    return [{**e, "authorizations": [{"id": i, "code": c} for i, c in sorted(by_entity.get(key(e), {}).items(), key=lambda x: x[1])]} for e in entries]


# ── the delivery ─────────────────────────────────────────────────────────


async def delivery_source(db: AsyncSession, material: Material) -> Baseline | None:
    """validation.DELIVERY_SOURCES: with a reviewed baseline, the delivery is its snapshot."""
    return await latest_reviewed(db, material)


async def delivery_guard(db: AsyncSession, material: Material) -> list[dict[str, Any]]:
    """validation.DELIVERY_GUARDS: no delivery without a reviewed baseline."""
    return [] if await latest_reviewed(db, material) is not None else [{"code": "delivery_no_baseline", "params": {}}]


validation.DELIVERY_SOURCES.append(delivery_source)
validation.DELIVERY_GUARDS.append(delivery_guard)


async def reviewer_name(db: AsyncSession, baseline: Baseline) -> str:
    return (await db.scalar(select(User.display_name).where(User.id == baseline.reviewed_by))) or "" if baseline.reviewed_by else ""


async def run_of(db: AsyncSession, baseline: Baseline) -> ValidationRun | None:
    return await db.get(ValidationRun, baseline.validation_run_id) if baseline.validation_run_id else None


# What a change of these models names in the diff (for the row's history).
ENTITY_OF = {PhysicalPosition: "row", FunctionalProduct: "product", ExtraFunction: "extra", Incompatibility: "incompatibility", ArticlePart: "part"}


# ── the book import ──────────────────────────────────────────────────────


async def import_guard(db: AsyncSession, material: Material, job: Any) -> None:
    """anexo_xi_import.IMPORT_GUARDS: applying a book to a CUF in review, or with a reviewed
    baseline without an approved authorization, is refused before anything is written (the
    write guard would catch the changes; this also refuses a book that changes nothing)."""
    from fastapi import HTTPException

    from app.core.errors import error_detail
    from app.services import changes

    st = {b.state for b in (await latest_reviewed(db, material), await in_review(db, material)) if b is not None}
    need = changes.required(st)
    if need == "locked":
        raise HTTPException(status_code=409, detail=error_detail("baseline_in_review"))
    if need == "authorization":
        wanted = changes.requested_authorization()
        item = await db.get(ChangeAuthorization, wanted) if wanted else None
        if item is None:
            raise HTTPException(status_code=409, detail=error_detail("authorization_required"))
        if item.material_id != material.id or item.state != "aprobada":
            # Another CUF's authorization is not named: its code carries that CUF's P/N.
            own = item.code if item.material_id == material.id else ""
            raise HTTPException(status_code=409, detail=error_detail("authorization_not_usable", authorization=own))


def _register_import_guard() -> None:
    from app.services import anexo_xi_import

    if import_guard not in anexo_xi_import.IMPORT_GUARDS:
        anexo_xi_import.IMPORT_GUARDS.append(import_guard)


_register_import_guard()
