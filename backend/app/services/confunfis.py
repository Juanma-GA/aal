"""The CONFUNFIS of a CUF (E13, RF-02): saving a row, its link with the
article master, its light observations, and what it adds to the extension
points of E11 and E12.

Saving a row (`save_row`), from the screen ("manual", strict) or a file
("seed" / "import", lenient):
- Only impossible data stops it: a QTY that is not a number, a CT SIGLE that
  is not S/N; and, from the screen, an SNS / CO / AL without its format or
  an SNS outside the CUF's normalized configuration. Anything else is kept
  and observed, so E16 finds it.
- The article (`link_article`): by NOC; without NOC, by P/N + NCAGE (its
  references); without either, by exact name among the articles with no NOC
  nor reference; otherwise a provisional article is created (origin
  "confunfis", audited). An article found by NOC without the row's P/N +
  NCAGE gets it as a reference (origin "confunfis"); a P/N + NCAGE another
  article has stays out of the row and is noted (OF-011). The master's SIGLE
  data are never touched; a name that differs from the master's is kept and
  observed (OF-009, NT §9.1.3 says which name to use).

Observations (`refresh_observations`, after every change of the
material's rows): provisional codes OF-001..OF-011 that E16 replaces by the
CF rules, kept on the rows (observations, observation_codes) for the
filters. The ranges of CO and AL come from the "confunfis" parameter; the
SNS format is the catalog's (E10).

Extension points: "Crear a partir de otro" copies the CONFUNFIS (source
"copia"); a subcategory whose SNS a row uses cannot leave the CUF; the
catalog version impact lists the rows whose SNS goes; "dónde se usa" lists
the positions of an article, in the materials the user may open.
"""

import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Article, ArticleReference, Material, PhysicalPosition, User
from app.services import audit, cuf
from app.services.articles import Checker, normalize_identity, reference_owner, register_usage
from app.services.catalog import SNS_RE
from app.services.confunfis_graph import ROOT, Graph, Row, key_text
from app.services.parameters import get_parameter
from app.services.permissions import accessible_materials

_TWO_DIGITS = re.compile(r"^\d{2}$")
OBSERVATION_CODES = (
    "OF-001",  # SNS outside the CUF's normalized configuration
    "OF-002",  # CS badly formed
    "OF-003",  # CS not found
    "OF-004",  # duplicate row (SNS + CO + AL + CS)
    "OF-005",  # CO or AL out of range
    "OF-006",  # QTY not a whole number, or < 1
    "OF-007",  # no NOC nor P/N
    "OF-008",  # no function
    "OF-009",  # name different from the master's
    "OF-010",  # on a cycle of CS
    "OF-011",  # its P/N + NCAGE belongs to another article
)
FIELDS = ("sns", "co", "al", "qty", "article_name", "function_text", "ct_sigle", "cs_sns", "cs_co", "cs_al")


class RowError(ValueError):
    """Data a row cannot hold: (field, code, params) each."""

    def __init__(self, problems: list[dict[str, Any]]):
        super().__init__("row_invalid")
        self.problems = problems


def name_key(name: str | None) -> str:
    return re.sub(r"\s+", " ", name or "").strip().casefold()


def _text(value: Any, *, upper: bool = False) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return (text.upper() if upper else text) or None


def snapshot(r: PhysicalPosition) -> dict[str, Any]:
    return {
        **{name: (str(getattr(r, name)) if name == "qty" and r.qty is not None else getattr(r, name)) for name in FIELDS},
        "article_id": str(r.article_id) if r.article_id else None,
        "article_reference_id": str(r.article_reference_id) if r.article_reference_id else None,
        "source": r.source,
    }


def graph_row(r: PhysicalPosition) -> Row:
    return Row(id=str(r.id), sns=r.sns, co=r.co, al=r.al, qty=r.qty, cs_sns=r.cs_sns, cs_co=r.cs_co, cs_al=r.cs_al)


async def live_rows(db: AsyncSession, material_id: uuid.UUID) -> list[PhysicalPosition]:
    query = select(PhysicalPosition).where(PhysicalPosition.material_id == material_id, PhysicalPosition.deleted_at.is_(None))
    return list((await db.execute(query.order_by(PhysicalPosition.sns, PhysicalPosition.co, PhysicalPosition.al, PhysicalPosition.created_at))).scalars())


# ── linking with the article master ─────────────────────────────────────


@dataclass
class Link:
    article: Article
    reference: ArticleReference | None
    notes: list[dict[str, Any]] = field(default_factory=list)
    created: bool = False


async def _by_name(db: AsyncSession, name: str | None) -> Article | None:
    """The article with no NOC nor reference of exactly this name (case and
    repeated spaces aside); the oldest if several."""
    key = name_key(name)
    if not key:
        return None
    with_refs = select(ArticleReference.article_id).where(ArticleReference.deleted_at.is_(None))
    candidates = (
        await db.execute(
            select(Article).where(Article.deleted_at.is_(None), Article.noc.is_(None), Article.id.not_in(with_refs)).order_by(Article.created_at)
        )
    ).scalars()
    return next((a for a in candidates if name_key(a.nombre) == key), None)


async def _attach_reference(db: AsyncSession, article: Article, pn: str | None, ncage: str | None, user_id: uuid.UUID | None, link: Link) -> None:
    if not pn:
        return
    own = next((r for r in article.live_references if (r.pn, r.ncage) == (pn, ncage)), None)
    if own is not None:
        link.reference = own
        return
    if await reference_owner(db, pn, ncage, exclude=article.id):
        link.notes.append({"code": "OF-011", "params": {"pn": pn, "ncage": ncage or ""}})
        return
    reference = ArticleReference(
        id=uuid.uuid4(), pn=pn, ncage=ncage, principal=article.principal_reference is None, origin="confunfis", version=1,
        created_by=user_id, updated_by=user_id,
    )
    article.references.append(reference)
    article.version += 1
    await db.flush()
    audit.record(
        db, action="article.reference_added", entity_type="article", entity_id=str(article.id), user_id=user_id,
        after={"reference": {"id": str(reference.id), "pn": pn, "ncage": ncage, "principal": reference.principal, "origin": "confunfis"}},
    )
    link.reference = reference


async def link_article(
    db: AsyncSession, *, noc: str | None, pn: str | None, ncage: str | None, name: str | None, user_id: uuid.UUID | None,
    material: Material, article_id: uuid.UUID | None = None,
) -> Link:
    article: Article | None = None
    if article_id is not None:
        article = (await db.execute(select(Article).where(Article.id == article_id, Article.deleted_at.is_(None)))).scalar_one_or_none()
        if article is None:
            raise RowError([{"field": "article_id", "code": "article_not_found", "params": {}}])
    elif noc:
        article = (await db.execute(select(Article).where(Article.noc == noc, Article.deleted_at.is_(None)))).scalar_one_or_none()
    elif pn:
        query = (
            select(Article)
            .join(ArticleReference, ArticleReference.article_id == Article.id)
            .where(ArticleReference.pn == pn, ArticleReference.deleted_at.is_(None), Article.deleted_at.is_(None))
        )
        query = query.where(ArticleReference.ncage == ncage) if ncage else query.where(ArticleReference.ncage.is_(None))
        article = (await db.execute(query.limit(1))).scalar_one_or_none()
    else:
        article = await _by_name(db, name)
    created = False
    if article is None:
        article = Article(
            id=uuid.uuid4(), noc=noc, nombre=name or "", origen_nombre="coloquial", origin="confunfis", version=1,
            created_by=user_id, updated_by=user_id, references=[], life_controls=[],
        )
        (await Checker.load(db)).recheck(article)
        db.add(article)
        await db.flush()
        audit.record(
            db, action="article.created", entity_type="article", entity_id=str(article.id), user_id=user_id,
            after={"noc": noc, "nombre": article.nombre, "origin": "confunfis", "material_id": str(material.id)},
        )
        created = True
    link = Link(article=article, reference=None, created=created)
    await _attach_reference(db, article, pn, ncage, user_id, link)
    return link


# ── saving a row ─────────────────────────────────────────────────────────


def _qty(value: Any, problems: list[dict[str, Any]]) -> Decimal | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        qty = Decimal(str(value).strip().replace(",", "."))
    except InvalidOperation:
        problems.append({"field": "qty", "code": "qty_not_a_number", "params": {}})
        return None
    if not qty.is_finite():
        problems.append({"field": "qty", "code": "qty_not_a_number", "params": {}})
        return None
    # 1.000000 read from a cell is 1; 1.50 is 1.5.
    return qty.to_integral_value() if qty == qty.to_integral_value() else qty.normalize()


# Problems of the value's type: always, whatever was changed.
_TYPE_CODES = {"qty_not_a_number", "yes_no", "required"}


def clean_values(
    values: dict[str, Any], *, strict: bool, config: set[str] | None, checked: set[str] | None = None
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """The row's values as stored, and what makes them impossible. `checked`:
    the fields an edit changes (the screen's checks of format and
    configuration apply to those only: a seeded row outside the
    configuration can still get its QTY corrected)."""
    problems: list[dict[str, Any]] = []
    out: dict[str, Any] = {
        "sns": _text(values.get("sns"), upper=True),
        "co": _text(values.get("co")),
        "al": _text(values.get("al")) or ("00" if strict else None),
        "qty": _qty(values.get("qty"), problems),
        "article_name": _text(values.get("article_name")),
        "function_text": _text(values.get("function_text")),
        "ct_sigle": _text(values.get("ct_sigle"), upper=True),
        "cs_sns": _text(values.get("cs_sns"), upper=True),
        "cs_co": _text(values.get("cs_co")),
        "cs_al": _text(values.get("cs_al")),
    }
    for name in ("sns", "co", "al"):
        if out[name] is None:
            problems.append({"field": name, "code": "required", "params": {}})
    if out["ct_sigle"] not in (None, "S", "N"):
        problems.append({"field": "ct_sigle", "code": "yes_no", "params": {}})
    if strict:
        if out["sns"] and not SNS_RE.match(out["sns"]):
            problems.append({"field": "sns", "code": "sns_format", "params": {}})
        elif out["sns"] and config is not None and out["sns"] not in config and (out["sns"], out["co"], out["al"]) != ROOT:
            problems.append({"field": "sns", "code": "sns_not_in_config", "params": {"sns": out["sns"]}})
        for name in ("co", "al"):
            if out[name] and not _TWO_DIGITS.match(out[name]):
                problems.append({"field": name, "code": "two_digits", "params": {}})
        cs = [out["cs_sns"], out["cs_co"], out["cs_al"]]
        if any(cs) and not (cs[0] and SNS_RE.match(cs[0]) and cs[1] and _TWO_DIGITS.match(cs[1]) and cs[2] and _TWO_DIGITS.match(cs[2])):
            problems.append({"field": "cs", "code": "cs_format", "params": {}})
    if checked is not None:
        problems = [p for p in problems if p["code"] in _TYPE_CODES or p["field"] in checked]
    return out, problems


async def save_row(
    db: AsyncSession, material: Material, values: dict[str, Any], user_id: uuid.UUID | None, *, source: str, strict: bool,
    row: PhysicalPosition | None = None, identity: dict[str, Any] | None = None, config: set[str] | None = None, audit_ip: str | None = None,
    checked: set[str] | None = None, action: str | None = None,
) -> PhysicalPosition:
    """Creates or changes a row (without refreshing the observations:
    `refresh_observations` once the batch is done). `identity`: the
    article's NOC, P/N, NCAGE (or its article_id) when it changes or for a
    new row."""
    if strict and config is None:
        config = set(await cuf.normalized_config(db, material))
    clean, problems = clean_values(values, strict=strict, config=config, checked=checked)
    link: Link | None = None
    if identity is not None:
        noc, pn, ncage, wrong = normalize_identity(identity.get("noc"), identity.get("pn"), identity.get("ncage"))
        problems += [{"field": w, "code": f"{w}_invalid", "params": {}} for w in wrong]
        if ncage and not pn:
            problems.append({"field": "pn", "code": "pn_required", "params": {}})
        if problems:
            raise RowError(problems)
        link = await link_article(
            db, noc=noc, pn=pn, ncage=ncage, name=clean["article_name"], user_id=user_id, material=material, article_id=identity.get("article_id")
        )
    elif problems:
        raise RowError(problems)
    before = snapshot(row) if row is not None else None
    if row is None:
        row = PhysicalPosition(id=uuid.uuid4(), material_id=material.id, source=source, version=1, created_by=user_id, updated_by=user_id)
        db.add(row)
    else:
        row.version += 1
        row.updated_by = user_id
    for name, value in clean.items():
        setattr(row, name, value)
    if link is not None:
        row.article_id = link.article.id
        row.article_reference_id = link.reference.id if link.reference else None
        row.link_notes = link.notes
        if not row.article_name:
            row.article_name = link.article.nombre
    await db.flush()
    audit.record(
        db, action=action or ("confunfis.row_updated" if before else "confunfis.row_created"), entity_type="physical_position", entity_id=str(row.id),
        user_id=user_id, material_id=material.id, before=before, after=snapshot(row), ip=audit_ip,
    )
    return row


# ── observations ─────────────────────────────────────────────────────────


def _out_of(value: str, bounds: dict[str, int]) -> bool:
    return not _TWO_DIGITS.match(value or "") or not bounds["min"] <= int(value) <= bounds["max"]


def observations_of(
    rows: list[PhysicalPosition], config: set[str], articles: dict[uuid.UUID, Article], params: dict[str, Any], graph: Graph | None = None
) -> dict[uuid.UUID, list[dict[str, Any]]]:
    graph = graph or Graph(graph_row(r) for r in rows)
    duplicates = graph.duplicates()
    out: dict[uuid.UUID, list[dict[str, Any]]] = {}
    for r in rows:
        found: list[dict[str, Any]] = []
        add = lambda code, **p: found.append({"code": code, "params": p})  # noqa: E731
        root = (r.sns, r.co, r.al) == ROOT
        cs = " ".join(x or "" for x in (r.cs_sns, r.cs_co, r.cs_al)).strip()
        if not root and r.sns not in config:
            add("OF-001", sns=r.sns)
        orphan = graph.orphan.get(str(r.id))
        if orphan == "malformed":
            add("OF-002", cs=cs)
        elif orphan == "not_found":
            add("OF-003", cs=cs)
        if str(r.id) in duplicates:
            add("OF-004")
        if _out_of(r.co, params["co"]) or _out_of(r.al, params["al"]):
            add("OF-005", co=r.co, al=r.al)
        if r.qty is None or r.qty != r.qty.to_integral_value() or r.qty < 1:
            add("OF-006", qty="" if r.qty is None else str(r.qty))
        article = articles.get(r.article_id) if r.article_id else None
        if article is None or (article.noc is None and r.article_reference_id is None):
            add("OF-007")
        if not r.function_text:
            add("OF-008")
        if article is not None and r.article_name and name_key(r.article_name) != name_key(article.nombre):
            add("OF-009", master=article.nombre)
        if graph.in_cycle(graph.rows[str(r.id)]):
            add("OF-010")
        found += [n for n in r.link_notes or [] if n.get("code") == "OF-011"]
        out[r.id] = found
    return out


async def articles_of(db: AsyncSession, rows: list[PhysicalPosition]) -> dict[uuid.UUID, Article]:
    ids = {r.article_id for r in rows if r.article_id}
    return {a.id: a for a in (await db.execute(select(Article).where(Article.id.in_(ids)))).scalars()} if ids else {}


async def refresh_observations(db: AsyncSession, material: Material) -> None:
    """Recomputes every row's observations (one row's change may change
    another's: a duplicate, a CS). Only the changed ones are written, not
    through the ORM: neither their version nor updated_at move."""
    rows = await live_rows(db, material.id)
    found = observations_of(rows, set(await cuf.normalized_config(db, material)), await articles_of(db, rows), await get_parameter(db, "confunfis"))
    for r in rows:
        if found[r.id] != r.observations:
            await db.execute(
                update(PhysicalPosition)
                .where(PhysicalPosition.id == r.id)
                .values(observations=found[r.id], observation_codes=sorted({o["code"] for o in found[r.id]}), updated_at=PhysicalPosition.updated_at)
                .execution_options(synchronize_session=False)
            )
            r.observations = found[r.id]
            r.observation_codes = sorted({o["code"] for o in found[r.id]})


# ── CUF montado ──────────────────────────────────────────────────────────


async def mounted(db: AsyncSession, material: Material, rows: list[PhysicalPosition], articles: dict[uuid.UUID, Article]) -> dict[uuid.UUID, Material]:
    """Row -> the other material whose CUF its article is (NOC, or P/N + NCAGE)."""
    others = (await db.execute(select(Material).where(Material.deleted_at.is_(None), Material.id != material.id))).scalars().all()
    by_noc = {m.noc: m for m in others if m.noc}
    by_pn = {(m.part_number, m.ncage): m for m in others if m.part_number and m.ncage}
    out: dict[uuid.UUID, Material] = {}
    for r in rows:
        a = articles.get(r.article_id) if r.article_id else None
        if a is None:
            continue
        found = by_noc.get(a.noc) if a.noc else None
        if found is None:
            found = next((by_pn[(ref.pn, ref.ncage)] for ref in a.live_references if (ref.pn, ref.ncage) in by_pn), None)
        if found is not None:
            out[r.id] = found
    return out


# ── extension points ─────────────────────────────────────────────────────


@cuf.register_copier("confunfis")
async def copy_confunfis(db: AsyncSession, source: Material, target: Material, options: cuf.CopyOptions, user_id: uuid.UUID | None = None) -> int:
    """Its rows, new, with the same articles (source "copia")."""
    rows = await live_rows(db, source.id)
    for r in rows:
        db.add(PhysicalPosition(
            id=uuid.uuid4(), material_id=target.id, source="copia", version=1, created_by=user_id, updated_by=user_id,
            article_id=r.article_id, article_reference_id=r.article_reference_id, link_notes=r.link_notes,
            **{name: getattr(r, name) for name in FIELDS},
        ))
    await db.flush()
    if rows:
        audit.record(
            db, action="confunfis.copied", entity_type="material", entity_id=str(target.id), user_id=user_id, material_id=target.id,
            after={"from": str(source.id), "rows": len(rows)},
        )
        await refresh_observations(db, target)
    return len(rows)


def _row_text(r: PhysicalPosition) -> str:
    return f"{r.sns} {r.co} {r.al} {r.article_name or ''}".strip()


async def rows_losing_sns(db: AsyncSession, material: Material, lost: set[str]) -> list[PhysicalPosition]:
    return [r for r in await live_rows(db, material.id) if r.sns in lost]


async def _subcategory_guard(db: AsyncSession, material: Material, removed: set[str]) -> tuple[str, dict[str, Any]] | None:
    """A subcategory cannot leave while a row uses an SNS only it brings."""
    config = await cuf.normalized_config(db, material)
    lost = {sns for sns, origins in config.items() if set(origins) <= removed}
    rows = await rows_losing_sns(db, material, lost)
    if not rows:
        return None
    return "subcategory_used_by_confunfis", {"count": len(rows), "rows": "; ".join(_row_text(r) for r in rows[:10])}


cuf.SUBCATEGORY_REMOVAL_GUARDS.append(_subcategory_guard)


async def _impact_rows(db: AsyncSession, material: Material, report: dict[str, Any]) -> dict[str, Any]:
    rows = await rows_losing_sns(db, material, set(report["removed"]))
    return {"confunfis_rows": [{"sns": r.sns, "co": r.co, "al": r.al, "name": r.article_name} for r in rows]}


cuf.IMPACT_EXTENSIONS.append(_impact_rows)


@register_usage("confunfis")
async def _positions_of(db: AsyncSession, article: Article, user: User) -> list[dict[str, Any]]:
    """Its CONFUNFIS positions, in the materials the user may open."""
    rows = (
        await db.execute(
            select(PhysicalPosition).where(PhysicalPosition.article_id == article.id, PhysicalPosition.deleted_at.is_(None))
            .order_by(PhysicalPosition.sns, PhysicalPosition.co, PhysicalPosition.al)
        )
    ).scalars().all()
    if not rows:
        return []
    names = {a.material.id: a.material.name for a in await accessible_materials(db, user)}
    return [
        {
            "kind": "confunfis_position", "material_id": str(r.material_id), "material_name": names[r.material_id], "row_id": str(r.id),
            "position": key_text((r.sns, r.co, r.al)),
            "cs": " ".join(x for x in (r.cs_sns, r.cs_co, r.cs_al) if x) or None,
        }
        for r in sorted(rows, key=lambda r: (names.get(r.material_id, ""), r.sns, r.co, r.al))
        if r.material_id in names
    ]


async def delete_row(db: AsyncSession, material: Material, row: PhysicalPosition, user_id: uuid.UUID | None, ip: str | None = None) -> None:
    before = snapshot(row)
    row.deleted_at, row.version, row.updated_by = datetime.now(UTC), row.version + 1, user_id
    audit.record(db, action="confunfis.row_deleted", entity_type="physical_position", entity_id=str(row.id), user_id=user_id, material_id=material.id, before=before, ip=ip)
