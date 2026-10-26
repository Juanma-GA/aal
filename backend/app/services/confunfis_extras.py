"""The rest of RF-02 (E14): the parts table of an article, the functional
products, the extra functions and the incompatibilities of a CUF
(app/models/confunfis_extras.py). Saving, the light observations (codes
provisional until the TP / PF / CF rules of E16) and what they add to the
extension points of E11-E13.

Observations:
- parts (OP-*): its own parent, a cycle of breakdowns, COP + ALP repeated,
  quantity < 1, the part also in the CONFUNFIS of a CUF that mounts its
  parent (the NT keeps parts out of the configuration), an ALP alone in its
  COP, a P/N + NCAGE of another article;
- functional products (OPF-*): POL code not in POL, designation other than
  its POL description (a notice), N/A/E not in NAE, supply unit not in D155,
  unit not in D112, a row identical to another;
- incompatibilities (OI-*): "excluye" between rows without alternatives on
  either side (one of them would be useless), "requiere" towards a removed
  row, a cycle of "requiere".

Only impossible data stop a save: types, the COP / ALP format from the
screen, a reference to a row of another CUF, an extra SNS outside the CUF's
configuration (or its row's own, or repeated), a criterion outside
CRITERIO_MULTIFUNCION.
"""

import re
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import set_committed_value

from app.models import (
    Article,
    ArticlePart,
    ExtraFunction,
    FunctionalProduct,
    Incompatibility,
    Material,
    PhysicalPosition,
    ReferenceValue,
    User,
)
from app.schemas.materials import normalize_code
from app.services import audit, confunfis, cuf
from app.services.articles import normalize_identity, register_usage
from app.services.confunfis_graph import Graph
from app.services.parameters import get_parameter
from app.services.permissions import accessible_materials
from app.services.reference import codes_by_state

_TWO_DIGITS = re.compile(r"^\d{2}$")
CRITERIA_TABLE = "CRITERIO_MULTIFUNCION"
PART_CODES = ("OP-001", "OP-002", "OP-003", "OP-004", "OP-005", "OP-006", "OP-007")
PRODUCT_CODES = ("OPF-001", "OPF-002", "OPF-003", "OPF-004", "OPF-005", "OPF-006")
INCOMPATIBILITY_CODES = ("OI-001", "OI-002", "OI-003")
PART_FIELDS = ("cop", "alp", "part_name", "quantity")
PRODUCT_FIELDS = ("designation", "pol_code", "nae", "noc", "supply_unit", "quantity", "unit")


class ExtraError(ValueError):
    """Data that cannot be stored: (field, code, params) each."""

    def __init__(self, problems: list[dict[str, Any]]):
        super().__init__("invalid")
        self.problems = problems


def _text(value: Any, *, upper: bool = False) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return (text.upper() if upper else text) or None


def _number(value: Any, field: str, problems: list[dict[str, Any]], *, bulk: bool = False) -> Decimal | None:
    """A quantity; empty (or "N/A" for a product in bulk) is None."""
    if value is None or (isinstance(value, str) and (not value.strip() or (bulk and value.strip().upper() in ("N/A", "NA")))):
        return None
    try:
        number = Decimal(str(value).strip().replace(",", "."))
    except InvalidOperation:
        problems.append({"field": field, "code": "not_a_number", "params": {}})
        return None
    if not number.is_finite() or abs(number) > 10**9:
        problems.append({"field": field, "code": "not_a_number", "params": {}})
        return None
    return number.to_integral_value() if number == number.to_integral_value() else number.normalize()


def _plain(value: Any) -> Any:
    return str(value) if isinstance(value, Decimal) else str(value) if isinstance(value, uuid.UUID) else value


def snapshot(obj: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    return {name: _plain(getattr(obj, name)) for name in fields}


def _observed(model: Any, obj: Any, found: list[dict[str, Any]]) -> Any:
    """The statement that writes `found` on `obj` without moving its
    version nor updated_at (and the instance keeps it as committed)."""
    codes = sorted({o["code"] for o in found})
    set_committed_value(obj, "observations", found)
    set_committed_value(obj, "observation_codes", codes)
    return (
        update(model).where(model.id == obj.id)
        .values(observations=found, observation_codes=codes, updated_at=model.updated_at)
        .execution_options(synchronize_session=False)
    )


def _cycles(edges: dict[Any, set[Any]]) -> set[Any]:
    """The nodes on a cycle of `edges` (node -> nodes it points to)."""
    on_cycle: set[Any] = set()
    state: dict[Any, int] = {}  # 1 visiting, 2 done
    for start in list(edges):
        if start in state:
            continue
        stack: list[tuple[Any, list[Any]]] = [(start, sorted(edges.get(start, ()), key=str))]
        path = [start]
        state[start] = 1
        while stack:
            node, todo = stack[-1]
            if todo:
                nxt = todo.pop()
                if state.get(nxt) == 1:
                    on_cycle.update(path[path.index(nxt):])
                elif nxt not in state:
                    state[nxt] = 1
                    path.append(nxt)
                    stack.append((nxt, sorted(edges.get(nxt, ()), key=str)))
                continue
            state[node] = 2
            stack.pop()
            path.pop()
    return on_cycle


# ── parts (§9.1.10) ──────────────────────────────────────────────────────


async def live_parts(db: AsyncSession, parent_id: uuid.UUID | None = None) -> list[ArticlePart]:
    query = select(ArticlePart).where(ArticlePart.deleted_at.is_(None))
    if parent_id is not None:
        query = query.where(ArticlePart.parent_article_id == parent_id)
    return list((await db.execute(query.order_by(ArticlePart.cop, ArticlePart.alp, ArticlePart.created_at))).scalars())


def clean_part(values: dict[str, Any], params: dict[str, Any], *, strict: bool, checked: set[str] | None = None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    problems: list[dict[str, Any]] = []
    out = {
        "cop": _text(values.get("cop")),
        "alp": _text(values.get("alp")) or ("00" if strict else None),
        "part_name": _text(values.get("part_name")),
        "quantity": _number(values.get("quantity"), "quantity", problems),
    }
    for name in ("cop", "alp"):
        if out[name] is None:
            problems.append({"field": name, "code": "required", "params": {}})
        elif strict and (checked is None or name in checked):
            bounds = params[name]
            if not _TWO_DIGITS.match(out[name]):
                problems.append({"field": name, "code": "two_digits", "params": {}})
            elif not bounds["min"] <= int(out[name]) <= bounds["max"]:
                problems.append({"field": name, "code": "out_of_range", "params": {"min": f"{bounds['min']:02d}", "max": f"{bounds['max']:02d}"}})
    return out, problems


async def save_part(
    db: AsyncSession, parent: Article, values: dict[str, Any], user_id: uuid.UUID | None, *, source: str, strict: bool,
    part: ArticlePart | None = None, identity: dict[str, Any] | None = None, checked: set[str] | None = None, ip: str | None = None,
) -> ArticlePart:
    params = await get_parameter(db, "confunfis")
    clean, problems = clean_part(values, params, strict=strict, checked=checked)
    link = None
    if identity is not None:
        noc, pn, ncage, wrong = normalize_identity(identity.get("noc"), identity.get("pn"), identity.get("ncage"))
        problems += [{"field": w, "code": f"{w}_invalid", "params": {}} for w in wrong]
        if ncage and not pn:
            problems.append({"field": "pn", "code": "pn_required", "params": {}})
        if problems:
            raise ExtraError(problems)
        try:
            link = await confunfis.link_article(
                db, noc=noc, pn=pn, ncage=ncage, name=clean["part_name"], user_id=user_id, material=None, article_id=identity.get("article_id"),
                ip=ip, origin={"parent_article_id": str(parent.id)},
            )
        except confunfis.RowError as exc:
            raise ExtraError(exc.problems) from None
    elif problems:
        raise ExtraError(problems)
    before = snapshot(part, (*PART_FIELDS, "part_article_id")) if part is not None else None
    if part is None:
        part = ArticlePart(id=uuid.uuid4(), parent_article_id=parent.id, source=source, version=1, created_by=user_id, updated_by=user_id)
        db.add(part)
    else:
        part.version += 1
        part.updated_by = user_id
    for name, value in clean.items():
        setattr(part, name, value)
    if link is not None:
        part.part_article_id = link.article.id
        part.article_reference_id = link.reference.id if link.reference else None
        part.link_notes = [{**n, "code": "OP-007"} for n in link.notes]
        if not part.part_name:
            part.part_name = link.article.nombre
    await db.flush()
    audit.record(
        db, action="article.part_updated" if before else "article.part_added", entity_type="article", entity_id=str(parent.id), user_id=user_id,
        before={"part": before} if before else None, after={"part": {"id": str(part.id), **snapshot(part, (*PART_FIELDS, "part_article_id"))}}, ip=ip,
    )
    return part


async def remove_part(db: AsyncSession, part: ArticlePart, user_id: uuid.UUID | None, ip: str | None) -> None:
    before = snapshot(part, (*PART_FIELDS, "part_article_id"))
    part.deleted_at, part.version, part.updated_by = datetime.now(UTC), part.version + 1, user_id
    audit.record(
        db, action="article.part_removed", entity_type="article", entity_id=str(part.parent_article_id), user_id=user_id,
        before={"part": {"id": str(part.id), **before}}, ip=ip,
    )


async def reset_alone_alp(db: AsyncSession, parent: Article, cop: str, user_id: uuid.UUID | None, ip: str | None) -> bool:
    """The ALP left alone (other than 00) in `cop` goes back to 00; False when there is none."""
    same = [p for p in await live_parts(db, parent.id) if p.cop == cop]
    alps = {p.alp for p in same}
    if len(alps) != 1 or "00" in alps:
        return False
    for p in same:
        await save_part(db, parent, {**snapshot(p, PART_FIELDS), "alp": "00"}, user_id, source=p.source, strict=False, part=p, ip=ip)
    return True


async def refresh_parts(db: AsyncSession) -> None:
    """Every part's observations: a cycle can cross any breakdown, and a
    part in a CONFUNFIS depends on every CUF that mounts its parent."""
    parts = await live_parts(db)
    if not parts:
        return
    edges: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
    for p in parts:
        if p.part_article_id:
            edges[p.parent_article_id].add(p.part_article_id)
    cyclic = _cycles(edges)
    # Materials each article sits in (its CONFUNFIS rows).
    ids = {p.parent_article_id for p in parts} | {p.part_article_id for p in parts if p.part_article_id}
    in_materials: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
    for article_id, material_id in await db.execute(
        select(PhysicalPosition.article_id, PhysicalPosition.material_id).where(PhysicalPosition.article_id.in_(ids), PhysicalPosition.deleted_at.is_(None))
    ):
        in_materials[article_id].add(material_id)
    keys: dict[tuple, list[uuid.UUID]] = defaultdict(list)
    alps: dict[tuple, set[str]] = defaultdict(set)
    for p in parts:
        keys[(p.parent_article_id, p.cop, p.alp)].append(p.id)
        alps[(p.parent_article_id, p.cop)].add(p.alp)
    for p in parts:
        found: list[dict[str, Any]] = []
        if p.part_article_id == p.parent_article_id:
            found.append({"code": "OP-001", "params": {}})
        elif p.part_article_id and p.part_article_id in cyclic and p.parent_article_id in cyclic:
            found.append({"code": "OP-002", "params": {}})
        if len(keys[(p.parent_article_id, p.cop, p.alp)]) > 1:
            found.append({"code": "OP-003", "params": {"cop": p.cop, "alp": p.alp}})
        if p.quantity is None or p.quantity < 1:
            found.append({"code": "OP-004", "params": {"quantity": "" if p.quantity is None else str(p.quantity)}})
        if p.part_article_id and in_materials[p.part_article_id] & in_materials[p.parent_article_id]:
            found.append({"code": "OP-005", "params": {}})
        if p.alp != "00" and len(alps[(p.parent_article_id, p.cop)]) == 1:
            found.append({"code": "OP-006", "params": {"alp": p.alp}})
        found += [n for n in p.link_notes or [] if n.get("code") == "OP-007"]
        if found != p.observations:
            await db.execute(_observed(ArticlePart, p, found))


def part_totals(graph: Graph, rows: list[PhysicalPosition], parts: list[ArticlePart]) -> dict[uuid.UUID, Decimal | None]:
    """Each part's total in the CUF: its quantity × the totals of the
    distinct huecos its parent sits in (an AL of the same hueco, once)."""
    huecos: dict[uuid.UUID, set[tuple[str, str]]] = defaultdict(set)
    for r in rows:
        if r.article_id:
            huecos[r.article_id].add((r.sns, r.co))
    out: dict[uuid.UUID, Decimal | None] = {}
    for p in parts:
        totals = [graph.total(h) for h in sorted(huecos.get(p.parent_article_id, ()))]
        known = [t for t in totals if t is not None]
        out[p.id] = p.quantity * sum(known, Decimal(0)) if known and p.quantity is not None else None
    return out


# ── functional products (§9.1.11) ────────────────────────────────────────


async def live_products(db: AsyncSession, material_id: uuid.UUID) -> list[FunctionalProduct]:
    query = select(FunctionalProduct).where(FunctionalProduct.material_id == material_id, FunctionalProduct.deleted_at.is_(None))
    return list((await db.execute(query.order_by(FunctionalProduct.pol_code, FunctionalProduct.nae, FunctionalProduct.created_at))).scalars())


def clean_product(values: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    problems: list[dict[str, Any]] = []
    noc = normalize_code(values.get("noc"))
    out = {
        "designation": _text(values.get("designation")),
        "pol_code": _text(values.get("pol_code"), upper=True),
        "nae": _text(values.get("nae"), upper=True),
        "noc": noc,
        "supply_unit": _text(values.get("supply_unit"), upper=True),
        "quantity": _number(values.get("quantity"), "quantity", problems, bulk=True),
        "unit": _text(values.get("unit"), upper=True),
    }
    if not out["designation"]:
        problems.append({"field": "designation", "code": "required", "params": {}})
    return out, problems


async def save_product(
    db: AsyncSession, material: Material, values: dict[str, Any], user_id: uuid.UUID | None, *, source: str,
    product: FunctionalProduct | None = None, ip: str | None = None,
) -> FunctionalProduct:
    clean, problems = clean_product(values)
    if problems:
        raise ExtraError(problems)
    before = snapshot(product, PRODUCT_FIELDS) if product is not None else None
    if product is None:
        product = FunctionalProduct(id=uuid.uuid4(), material_id=material.id, source=source, version=1, created_by=user_id, updated_by=user_id)
        db.add(product)
    else:
        product.version += 1
        product.updated_by = user_id
    for name, value in clean.items():
        setattr(product, name, value)
    # Linked with the master when the article exists; never a provisional one.
    product.article_id = (
        await db.scalar(select(Article.id).where(Article.noc == clean["noc"], Article.deleted_at.is_(None))) if clean["noc"] else None
    )
    await db.flush()
    audit.record(
        db, action="confunfis.product_updated" if before else "confunfis.product_added", entity_type="functional_product", entity_id=str(product.id),
        user_id=user_id, material_id=material.id, before=before, after=snapshot(product, PRODUCT_FIELDS), ip=ip,
    )
    return product


async def remove_product(db: AsyncSession, material: Material, product: FunctionalProduct, user_id: uuid.UUID | None, ip: str | None) -> None:
    before = snapshot(product, PRODUCT_FIELDS)
    product.deleted_at, product.version, product.updated_by = datetime.now(UTC), product.version + 1, user_id
    audit.record(db, action="confunfis.product_removed", entity_type="functional_product", entity_id=str(product.id), user_id=user_id, material_id=material.id, before=before, ip=ip)


def _name_key(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip().casefold()


async def refresh_products(db: AsyncSession, material: Material) -> None:
    products = await live_products(db, material.id)
    if not products:
        return
    pol = await codes_by_state(db, "POL")
    nae, d155, d112 = [await codes_by_state(db, t) for t in ("NAE", "D155", "D112")]
    codes = {p.pol_code for p in products if p.pol_code}
    descriptions = dict(
        (await db.execute(select(ReferenceValue.code, ReferenceValue.description).where(ReferenceValue.table_code == "POL", ReferenceValue.code.in_(codes)))).all()
    ) if codes else {}
    same: dict[tuple, list[uuid.UUID]] = defaultdict(list)
    for p in products:
        same[tuple(_plain(getattr(p, f)) for f in PRODUCT_FIELDS)].append(p.id)
    for p in products:
        found: list[dict[str, Any]] = []
        if p.pol_code and not pol.get(p.pol_code):
            found.append({"code": "OPF-001", "params": {"pol": p.pol_code}})
        elif p.pol_code and _name_key(descriptions.get(p.pol_code)) != _name_key(p.designation):
            found.append({"code": "OPF-002", "params": {"pol": p.pol_code, "description": descriptions.get(p.pol_code) or ""}})
        if p.nae and not nae.get(p.nae):
            found.append({"code": "OPF-003", "params": {"nae": p.nae}})
        if p.supply_unit and not d155.get(p.supply_unit):
            found.append({"code": "OPF-004", "params": {"unit": p.supply_unit}})
        if p.unit and not d112.get(p.unit):
            found.append({"code": "OPF-005", "params": {"unit": p.unit}})
        if len(same[tuple(_plain(getattr(p, f)) for f in PRODUCT_FIELDS)]) > 1:
            found.append({"code": "OPF-006", "params": {}})
        if found != p.observations:
            await db.execute(_observed(FunctionalProduct, p, found))


# ── extra functions (§9.1.1) ─────────────────────────────────────────────


async def live_extras(db: AsyncSession, material_id: uuid.UUID) -> list[ExtraFunction]:
    query = select(ExtraFunction).where(ExtraFunction.material_id == material_id, ExtraFunction.deleted_at.is_(None))
    return list((await db.execute(query.order_by(ExtraFunction.sns, ExtraFunction.created_at))).scalars())


async def check_extra(
    db: AsyncSession, material: Material, row: PhysicalPosition, sns: str, criterion: str, current: ExtraFunction | None = None
) -> list[dict[str, Any]]:
    problems: list[dict[str, Any]] = []
    config = await cuf.normalized_config(db, material)
    if sns not in config:
        problems.append({"field": "sns", "code": "sns_not_in_config", "params": {"sns": sns}})
    elif sns == row.sns:
        problems.append({"field": "sns", "code": "sns_of_the_row", "params": {"sns": sns}})
    elif any(e.sns == sns and e.position_id == row.id and e is not current for e in await live_extras(db, material.id)):
        problems.append({"field": "sns", "code": "sns_repeated", "params": {"sns": sns}})
    criteria = await codes_by_state(db, CRITERIA_TABLE)
    if not criteria.get(criterion) and not (current is not None and current.criterion == criterion):
        problems.append({"field": "criterion", "code": "not_in_table", "params": {"table": CRITERIA_TABLE}})
    return problems


async def add_extra(
    db: AsyncSession, material: Material, row: PhysicalPosition, sns: str, criterion: str, comment: str | None, user_id: uuid.UUID | None,
    *, source: str = "manual", ip: str | None = None,
) -> ExtraFunction:
    """A checked extra function (check_extra), stored and audited."""
    extra = ExtraFunction(
        id=uuid.uuid4(), material_id=material.id, position_id=row.id, sns=sns, criterion=criterion, comment=(comment or "").strip() or None,
        source=source, version=1, created_by=user_id, updated_by=user_id,
    )
    db.add(extra)
    await db.flush()
    audit.record(db, action="confunfis.extra_function_added", entity_type="extra_function", entity_id=str(extra.id), user_id=user_id, material_id=material.id, after=extra_snapshot(extra), ip=ip)
    return extra


def extra_snapshot(e: ExtraFunction) -> dict[str, Any]:
    return {"position_id": str(e.position_id), "sns": e.sns, "criterion": e.criterion, "comment": e.comment}


# ── incompatibilities ────────────────────────────────────────────────────


async def live_incompatibilities(db: AsyncSession, material_id: uuid.UUID) -> list[Incompatibility]:
    query = select(Incompatibility).where(Incompatibility.material_id == material_id, Incompatibility.deleted_at.is_(None))
    return list((await db.execute(query.order_by(Incompatibility.created_at))).scalars())


def incompatibility_snapshot(i: Incompatibility) -> dict[str, Any]:
    return {"row_a_id": str(i.row_a_id), "row_b_id": str(i.row_b_id), "kind": i.kind, "reason": i.reason}


async def add_incompatibility(
    db: AsyncSession, material: Material, a: PhysicalPosition, b: PhysicalPosition, kind: str, reason: str, user_id: uuid.UUID | None,
    *, source: str = "manual", ip: str | None = None,
) -> Incompatibility:
    item = Incompatibility(
        id=uuid.uuid4(), material_id=material.id, row_a_id=a.id, row_b_id=b.id, kind=kind, reason=reason, source=source, version=1,
        created_by=user_id, updated_by=user_id,
    )
    db.add(item)
    await db.flush()
    audit.record(db, action="confunfis.incompatibility_added", entity_type="incompatibility", entity_id=str(item.id), user_id=user_id, material_id=material.id, after=incompatibility_snapshot(item), ip=ip)
    return item


def same_incompatibility(i: Incompatibility, a: uuid.UUID, b: uuid.UUID, kind: str) -> bool:
    """"excluye" is symmetric: A-B is B-A."""
    if i.kind != kind:
        return False
    return (i.row_a_id, i.row_b_id) == (a, b) or (kind == "excluye" and (i.row_a_id, i.row_b_id) == (b, a))


async def refresh_incompatibilities(db: AsyncSession, material: Material, rows: list[PhysicalPosition], graph: Graph) -> None:
    items = await live_incompatibilities(db, material.id)
    if not items:
        return
    live = {str(r.id) for r in rows}
    requires: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
    for i in items:
        if i.kind == "requiere":
            requires[i.row_a_id].add(i.row_b_id)
    cyclic = _cycles(requires)
    for i in items:
        found: list[dict[str, Any]] = []
        a, b = graph.rows.get(str(i.row_a_id)), graph.rows.get(str(i.row_b_id))
        if i.kind == "excluye" and a and b and not graph.is_alternative(a) and not graph.is_alternative(b):
            found.append({"code": "OI-001", "params": {}})
        if i.kind == "requiere" and str(i.row_b_id) not in live:
            found.append({"code": "OI-002", "params": {}})
        if i.kind == "requiere" and i.row_a_id in cyclic and i.row_b_id in cyclic:
            found.append({"code": "OI-003", "params": {}})
        if found != i.observations:
            await db.execute(_observed(Incompatibility, i, found))


confunfis.REFRESH_EXTENSIONS.append(refresh_incompatibilities)


async def _refresh_parts(db: AsyncSession, material: Material, rows: list[PhysicalPosition], graph: Graph) -> None:
    """A row changed: which parts also sit in a CONFUNFIS may have too."""
    await refresh_parts(db)


confunfis.REFRESH_EXTENSIONS.append(_refresh_parts)


# ── extension points ─────────────────────────────────────────────────────


async def _copy(db: AsyncSession, source: Material, target: Material, mapping: dict[uuid.UUID, uuid.UUID], user_id: uuid.UUID | None) -> None:
    """Functional products, extra functions and incompatibilities, onto the
    copied rows (`mapping`: source row -> its copy). Parts are the
    article's: they are not copied."""
    await copy_extras(db, source, target, mapping, user_id)


async def copy_extras(db: AsyncSession, source: Material, target: Material, mapping: dict[uuid.UUID, uuid.UUID], user_id: uuid.UUID | None) -> dict[str, int]:
    products = await live_products(db, source.id)
    for p in products:
        db.add(FunctionalProduct(
            id=uuid.uuid4(), material_id=target.id, source="copia", version=1, created_by=user_id, updated_by=user_id, article_id=p.article_id,
            observations=p.observations, observation_codes=p.observation_codes, **{f: getattr(p, f) for f in PRODUCT_FIELDS},
        ))
    extras = [e for e in await live_extras(db, source.id) if e.position_id in mapping]
    for e in extras:
        db.add(ExtraFunction(
            id=uuid.uuid4(), material_id=target.id, position_id=mapping[e.position_id], sns=e.sns, criterion=e.criterion, comment=e.comment,
            source="copia", version=1, created_by=user_id, updated_by=user_id,
        ))
    incompatibilities = [i for i in await live_incompatibilities(db, source.id) if i.row_a_id in mapping and i.row_b_id in mapping]
    for i in incompatibilities:
        db.add(Incompatibility(
            id=uuid.uuid4(), material_id=target.id, row_a_id=mapping[i.row_a_id], row_b_id=mapping[i.row_b_id], kind=i.kind, reason=i.reason,
            source="copia", version=1, created_by=user_id, updated_by=user_id,
        ))
    await db.flush()
    counts = {"products": len(products), "extra_functions": len(extras), "incompatibilities": len(incompatibilities)}
    if any(counts.values()):
        audit.record(db, action="confunfis.extras_copied", entity_type="material", entity_id=str(target.id), user_id=user_id, material_id=target.id, after={"from": str(source.id), **counts})
    return counts


confunfis.COPY_EXTENSIONS.append(_copy)


async def remove_extra(db: AsyncSession, material: Material, e: ExtraFunction, user_id: uuid.UUID | None, ip: str | None, with_row: uuid.UUID | None = None) -> None:
    e.deleted_at, e.version, e.updated_by = datetime.now(UTC), e.version + 1, user_id
    audit.record(
        db, action="confunfis.extra_function_removed", entity_type="extra_function", entity_id=str(e.id), user_id=user_id, material_id=material.id,
        before=extra_snapshot(e), after={"with_row": str(with_row)} if with_row else None, ip=ip,
    )


async def remove_incompatibility(
    db: AsyncSession, material: Material, i: Incompatibility, user_id: uuid.UUID | None, ip: str | None, with_row: uuid.UUID | None = None
) -> None:
    i.deleted_at, i.version, i.updated_by = datetime.now(UTC), i.version + 1, user_id
    audit.record(
        db, action="confunfis.incompatibility_removed", entity_type="incompatibility", entity_id=str(i.id), user_id=user_id, material_id=material.id,
        before=incompatibility_snapshot(i), after={"with_row": str(with_row)} if with_row else None, ip=ip,
    )


async def _remove_with_row(db: AsyncSession, material: Material, row: PhysicalPosition, user_id: uuid.UUID | None, ip: str | None) -> None:
    """A row removed takes its extra functions and incompatibilities along."""
    for e in await live_extras(db, material.id):
        if e.position_id == row.id:
            await remove_extra(db, material, e, user_id, ip, with_row=row.id)
    for i in await live_incompatibilities(db, material.id):
        if row.id in (i.row_a_id, i.row_b_id):
            await remove_incompatibility(db, material, i, user_id, ip, with_row=row.id)


confunfis.ROW_REMOVAL_EXTENSIONS.append(_remove_with_row)


async def _extra_function_guard(db: AsyncSession, material: Material, removed: set[str]) -> tuple[str, dict[str, Any]] | None:
    """A subcategory cannot leave while an extra function uses an SNS only it brings."""
    config = await cuf.normalized_config(db, material)
    lost = {sns for sns, origins in config.items() if set(origins) <= removed}
    extras = [e for e in await live_extras(db, material.id) if e.sns in lost]
    if not extras:
        return None
    rows = {r.id: r for r in await confunfis.live_rows(db, material.id)}
    text = "; ".join(f"{e.sns} ({rows[e.position_id].sns} {rows[e.position_id].co} {rows[e.position_id].al})" for e in extras[:10] if e.position_id in rows)
    return "subcategory_used_by_extra_function", {"count": len(extras), "rows": text}


cuf.SUBCATEGORY_REMOVAL_GUARDS.append(_extra_function_guard)


@register_usage("parts")
async def _part_of(db: AsyncSession, article: Article, user: User) -> list[dict[str, Any]]:
    """Its parents in the parts table (the master is global: no material)."""
    rows = (
        await db.execute(
            select(ArticlePart, Article.nombre)
            .join(Article, Article.id == ArticlePart.parent_article_id)
            .where(ArticlePart.part_article_id == article.id, ArticlePart.deleted_at.is_(None), Article.deleted_at.is_(None))
            .order_by(Article.nombre, ArticlePart.cop, ArticlePart.alp)
        )
    ).all()
    return [{"kind": "part_of", "article_id": str(p.parent_article_id), "article_name": name, "cop": p.cop, "alp": p.alp} for p, name in rows]


@register_usage("functional_products")
async def _product_of(db: AsyncSession, article: Article, user: User) -> list[dict[str, Any]]:
    """The CUF it is a functional product of, those the user may open."""
    products = (
        await db.execute(select(FunctionalProduct).where(FunctionalProduct.article_id == article.id, FunctionalProduct.deleted_at.is_(None)))
    ).scalars().all()
    if not products:
        return []
    names = {a.material.id: a.material.name for a in await accessible_materials(db, user)}
    return [
        {"kind": "functional_product", "material_id": str(p.material_id), "material_name": names[p.material_id], "pol_code": p.pol_code, "nae": p.nae}
        for p in sorted(products, key=lambda p: (names.get(p.material_id, ""), p.pol_code or ""))
        if p.material_id in names
    ]


async def parents_of(db: AsyncSession, article_id: uuid.UUID) -> str:
    """The articles whose breakdown has this one as a part, as text ("" if none)."""
    names = (
        await db.execute(
            select(Article.nombre).join(ArticlePart, ArticlePart.parent_article_id == Article.id)
            .where(ArticlePart.part_article_id == article_id, ArticlePart.deleted_at.is_(None), Article.deleted_at.is_(None)).distinct()
        )
    ).scalars().all()
    return "; ".join(sorted(names)[:10])


async def parts_using_reference(db: AsyncSession, reference_id: uuid.UUID) -> bool:
    found = await db.scalar(select(ArticlePart.id).where(ArticlePart.article_reference_id == reference_id, ArticlePart.deleted_at.is_(None)).limit(1))
    return found is not None


async def unlink_products(db: AsyncSession, article_id: uuid.UUID) -> None:
    """An article removed: the functional products keep its NOC, unlinked."""
    await db.execute(update(FunctionalProduct).where(FunctionalProduct.article_id == article_id).values(article_id=None).execution_options(synchronize_session=False))
