"""The CONFUNFIS of a material (E13, RF-02): the physical tree (lazy, by
CS), the functional view (the CUF's normalized configuration with the rows
of each SNS), the flat table with its filters, a row's card, and adding,
editing, removing, "duplicar como alternativo" and "añadir CS alternativo",
each with its version and audited. Reading needs confunfis.ver, writing
confunfis.editar (the analyst), from the matrix (D5).

Every answer is computed from the material's rows as they are (the graph,
app/services/confunfis_graph.py); the observations are refreshed after each
change (app/services/confunfis.py).
"""

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, require_material_permission
from app.api.routes.catalog import like_text
from app.api.routes.users import confirmation_required, version_conflict
from app.core.errors import error_detail
from app.db.base import get_db
from app.models import Article, ArticlePart, AuditLog, Baseline, ExtraFunction, Incompatibility, Material, PhysicalPosition, SnsPosition, User
from app.schemas.confunfis import (
    AlternativeCsIn,
    ArticleBrief,
    ChainStep,
    FunctionalLevel,
    FunctionalNode,
    MaterialBrief,
    NextSlot,
    PathStep,
    RowDetail,
    RowIn,
    RowOut,
    RowPage,
    RowUpdate,
    SearchHit,
    SearchResult,
    Summary,
    TreeLevel,
    VersionIn,
)
from app.schemas.confunfis_extras import CufPartOut, ExtraFunctionOut, IncompatibilityOut, PartOut, RowRef
from app.services import audit, confunfis, cuf, validation
from app.services import confunfis_extras as extras
from app.services.catalog_tree import tree_level
from app.services.confunfis_graph import ROOT, Graph, key_text, well_formed
from app.services.parameters import get_parameter
from app.services.permissions import MaterialAccess, accessible_materials
from app.services.snapshots import client_ip
from app.validacion.catalog import BY_CODE

router = APIRouter(prefix="/api/materials/{material_id}/confunfis", tags=["confunfis"])

READ = "confunfis.ver"
EDIT = "confunfis.editar"
_IDENTITY = ("article_id", "noc", "pn", "ncage")


def _plain(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


@dataclass
class Context:
    """The material's rows and everything computed from them, once per request."""

    material: Material
    rows: list[PhysicalPosition]
    graph: Graph
    articles: dict[uuid.UUID, Article]
    names: dict[str, str]
    # Row -> the material whose CUF it is; `visible`: those the user may open.
    mounted: dict[uuid.UUID, Material]
    visible: set[uuid.UUID]
    # E14: what hangs from the rows; `gone`, removed rows an incompatibility still names.
    extras: list[ExtraFunction]
    incompatibilities: list[Incompatibility]
    gone: dict[uuid.UUID, PhysicalPosition]

    def by_id(self, row_id: uuid.UUID) -> PhysicalPosition:
        found = next((r for r in self.rows if r.id == row_id), None)
        if found is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_detail("confunfis_row_not_found"))
        return found


async def _context(db: AsyncSession, material: Material, user: User) -> Context:
    rows = await confunfis.live_rows(db, material.id)
    articles = await confunfis.articles_of(db, rows)
    names: dict[str, str] = {}
    if material.catalog_version_id and rows:
        sns = {r.sns for r in rows} | {r.cs_sns for r in rows if r.cs_sns}
        names = dict((await db.execute(select(SnsPosition.sns, SnsPosition.name).where(SnsPosition.version_id == material.catalog_version_id, SnsPosition.sns.in_(sns)))).all())
    names[ROOT[0]] = material.name
    visible = {a.material.id for a in await accessible_materials(db, user)}
    mounted = await confunfis.mounted(db, material, rows, articles)
    extra_rows = await extras.live_extras(db, material.id)
    incompatibilities = await extras.live_incompatibilities(db, material.id)
    live = {r.id for r in rows}
    missing = {i for x in incompatibilities for i in (x.row_a_id, x.row_b_id) if i not in live}
    gone = {r.id: r for r in (await db.execute(select(PhysicalPosition).where(PhysicalPosition.id.in_(missing), PhysicalPosition.material_id == material.id))).scalars()} if missing else {}
    if material.catalog_version_id and extra_rows:
        more = {e.sns for e in extra_rows} - set(names)
        if more:
            names.update(dict((await db.execute(select(SnsPosition.sns, SnsPosition.name).where(SnsPosition.version_id == material.catalog_version_id, SnsPosition.sns.in_(more)))).all()))
    return Context(material, rows, Graph(confunfis.graph_row(r) for r in rows), articles, names, mounted, visible, extra_rows, incompatibilities, gone)


def article_brief(a: Article | None, reference_id: uuid.UUID | None) -> ArticleBrief | None:
    if a is None:
        return None
    ref = next((x for x in a.live_references if x.id == reference_id), None)
    return ArticleBrief(id=a.id, noc=a.noc, pn=ref.pn if ref else None, ncage=ref.ncage if ref else None, nombre=a.nombre, origin=a.origin)


def part_out(p: ArticlePart, articles: dict[uuid.UUID, Article], alps: dict[tuple[uuid.UUID, str], set[str]]) -> PartOut:
    return PartOut(
        id=p.id, parent_article_id=p.parent_article_id, cop=p.cop, alp=p.alp, quantity=_plain(p.quantity), part_name=p.part_name,
        article=article_brief(articles.get(p.part_article_id) if p.part_article_id else None, p.article_reference_id),
        source=p.source, observations=p.observations, observation_codes=list(p.observation_codes),
        alternative=len(alps.get((p.parent_article_id, p.cop), set())) > 1, version=p.version, updated_at=p.updated_at,
    )


async def articles_by_id(db: AsyncSession, ids: set[uuid.UUID | None]) -> dict[uuid.UUID, Article]:
    ids = {i for i in ids if i}
    return {a.id: a for a in (await db.execute(select(Article).where(Article.id.in_(ids)))).scalars()} if ids else {}


def alps_of(parts: list[ArticlePart]) -> dict[tuple[uuid.UUID, str], set[str]]:
    out: dict[tuple[uuid.UUID, str], set[str]] = {}
    for p in parts:
        out.setdefault((p.parent_article_id, p.cop), set()).add(p.alp)
    return out


async def cuf_parts(db: AsyncSession, ctx: Context, parent_ids: set[uuid.UUID] | None = None) -> list[CufPartOut]:
    """The parts of the articles in the CUF's rows (or of `parent_ids`), with
    their parent's positions and their total in the CUF."""
    in_rows = {r.article_id for r in ctx.rows if r.article_id}
    wanted = in_rows if parent_ids is None else parent_ids & in_rows
    if not wanted:
        return []
    parts = [p for p in await extras.live_parts(db) if p.parent_article_id in wanted]
    totals = extras.part_totals(ctx.graph, ctx.rows, parts)
    articles = {**ctx.articles, **await articles_by_id(db, {p.part_article_id for p in parts} - set(ctx.articles))}
    positions: dict[uuid.UUID, list[str]] = {}
    for r in _ordered(ctx.rows):
        if r.article_id:
            positions.setdefault(r.article_id, []).append(key_text((r.sns, r.co, r.al)))
    alps = alps_of(parts)
    out = [
        CufPartOut(
            **part_out(p, articles, alps).model_dump(), parent=article_brief(ctx.articles[p.parent_article_id], None),
            parent_positions=positions.get(p.parent_article_id, []), total=_plain(totals.get(p.id)),
        )
        for p in parts
    ]
    return sorted(out, key=lambda x: (x.parent.nombre, x.cop, x.alp, str(x.id)))


def row_ref(ctx: Context, row_id: uuid.UUID) -> RowRef:
    r = next((x for x in ctx.rows if x.id == row_id), None) or ctx.gone.get(row_id)
    if r is None:
        return RowRef(id=row_id, position="", name=None, deleted=True)
    a = ctx.articles.get(r.article_id) if r.article_id else None
    return RowRef(id=r.id, position=key_text((r.sns, r.co, r.al)), name=r.article_name or (a.nombre if a else None), deleted=r.deleted_at is not None)


def extra_out(ctx: Context, e: ExtraFunction) -> ExtraFunctionOut:
    return ExtraFunctionOut(
        id=e.id, row=row_ref(ctx, e.position_id), sns=e.sns, sns_name=ctx.names.get(e.sns), criterion=e.criterion, comment=e.comment,
        source=e.source, version=e.version, updated_at=e.updated_at,
    )


def incompatibility_out(ctx: Context, i: Incompatibility) -> IncompatibilityOut:
    return IncompatibilityOut(
        id=i.id, row_a=row_ref(ctx, i.row_a_id), row_b=row_ref(ctx, i.row_b_id), kind=i.kind, reason=i.reason, source=i.source,
        observations=i.observations, observation_codes=list(i.observation_codes), version=i.version, updated_at=i.updated_at,
    )


def _row_out(ctx: Context, r: PhysicalPosition) -> RowOut:
    a = ctx.articles.get(r.article_id) if r.article_id else None
    g = ctx.graph.rows[str(r.id)]
    m = ctx.mounted.get(r.id)
    link = m if m is not None and m.id in ctx.visible else None
    return RowOut(
        id=r.id, sns=r.sns, co=r.co, al=r.al, qty=_plain(r.qty), sns_name=ctx.names.get(r.sns),
        article=article_brief(a, r.article_reference_id),
        article_name=r.article_name, function_text=r.function_text, ct_sigle=r.ct_sigle, cs_sns=r.cs_sns, cs_co=r.cs_co, cs_al=r.cs_al,
        source=r.source, observations=r.observations, observation_codes=list(r.observation_codes),
        total=_plain(ctx.graph.total(g.hueco)), orphan=ctx.graph.orphan.get(str(r.id)),
        alternative=ctx.graph.is_alternative(g), cs_alternative=ctx.graph.is_cs_alternative(g),
        child_count=len(ctx.graph.children.get(g.key, [])),
        is_mounted=link is not None, mounted=MaterialBrief(id=link.id, name=link.name) if link else None,
        extra_function_count=sum(1 for e in ctx.extras if e.position_id == r.id),
        incompatibility_count=sum(1 for i in ctx.incompatibilities if r.id in (i.row_a_id, i.row_b_id)),
        version=r.version, updated_at=r.updated_at,
    )


def _ordered(rows: list[Any]) -> list[Any]:
    return sorted(rows, key=lambda r: (r.sns, r.co, r.al, r.cs_sns or "", r.cs_co or "", r.cs_al or "", str(r.id)))


def _parse_key(text: str) -> tuple[str, str, str]:
    parts = text.split()
    if len(parts) != 3 or not well_formed(*parts):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=error_detail("confunfis_position_invalid"))
    return parts[0], parts[1], parts[2]


@router.get("/summary", response_model=Summary)
async def summary(access: MaterialAccess = Depends(require_material_permission(READ)), db: AsyncSession = Depends(get_db)) -> Summary:
    rows = await confunfis.live_rows(db, access.material.id)
    config = set(await cuf.normalized_config(db, access.material))
    extra_rows = await extras.live_extras(db, access.material.id)
    incompatibilities = await extras.live_incompatibilities(db, access.material.id)
    by_code: dict[str, int] = {}
    rules = await validation.settings(db)
    severities = {"bloqueante": 0, "aviso": 0}
    for r in rows:
        for code in r.observation_codes:
            by_code[code] = by_code.get(code, 0) + 1
        for o in r.observations:
            code = o.get("code")
            severity = validation.severity_of(rules.get(code), code) if code in BY_CODE else None
            if severity in severities:
                severities[severity] += 1
    return Summary(errors=severities["bloqueante"], warnings=severities["aviso"],
        rows=len(rows), positions=len({(r.sns, r.co, r.al) for r in rows}), huecos=len({(r.sns, r.co) for r in rows}),
        sns_covered=len({r.sns for r in rows} & config), sns_in_config=len(config),
        with_observations=sum(1 for r in rows if r.observation_codes), by_observation=dict(sorted(by_code.items())),
        sns_covered_by_extra=len(({e.sns for e in extra_rows} & config) - {r.sns for r in rows}),
        products=len(await extras.live_products(db, access.material.id)),
        multifunction_rows=len({e.position_id for e in extra_rows}),
        incompatibility_rows=len({i for x in incompatibilities for i in (x.row_a_id, x.row_b_id)} & {r.id for r in rows}),
    )


@router.get("/tree", response_model=TreeLevel)
async def tree(
    parent: str | None = Query(default=None, max_length=40),
    access: MaterialAccess = Depends(require_material_permission(READ)),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> TreeLevel:
    """The rows hanging from `parent` ("SNS CO AL"; the CUF, 000000 01 00,
    when absent). Alternatives come together (by SNS, CO, AL); a row with
    alternative CS appears under each of them."""
    ctx = await _context(db, access.material, user)
    key = _parse_key(parent) if parent else ROOT
    by_id = {str(r.id): r for r in ctx.rows}
    items = [by_id[g.id] for g in ctx.graph.children.get(key, [])]
    level = TreeLevel(parent=key_text(key), items=[_row_out(ctx, r) for r in _ordered(items)])
    if parent is None:
        root = next((r for r in ctx.rows if (r.sns, r.co, r.al) == ROOT), None)
        level.root = _row_out(ctx, root) if root else None
        level.orphans = [_row_out(ctx, by_id[rid]) for rid in sorted(ctx.graph.orphan, key=lambda i: (by_id[i].sns, by_id[i].co))]
        level.cycles = sorted(" ".join(h) for h in ctx.graph.cycle_huecos)
    return level


@router.get("/functional", response_model=FunctionalLevel)
async def functional(
    parent: str | None = Query(default=None, min_length=6, max_length=6),
    access: MaterialAccess = Depends(require_material_permission(READ)),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> FunctionalLevel:
    """One level of the CUF's normalized configuration, each SNS with its
    rows (and those of the SNS below it); at the top, the rows outside it."""
    material = access.material
    config = await cuf.normalized_config(db, material)
    rows = await confunfis.live_rows(db, material.id)
    count: dict[str, int] = {}
    for r in rows:
        count[r.sns] = count.get(r.sns, 0) + 1
    # E14: an SNS may be covered by the extra function of a row elsewhere.
    live = {r.id for r in rows}
    extra_count: dict[str, int] = {}
    for e in await extras.live_extras(db, material.id):
        if e.position_id in live:
            extra_count[e.sns] = extra_count.get(e.sns, 0) + 1
    items: list[FunctionalNode] = []
    if config:
        pairs = dict((await db.execute(select(SnsPosition.sns, SnsPosition.parent_sns).where(SnsPosition.version_id == material.catalog_version_id, SnsPosition.sns.in_(list(config))))).all())

        def up(counts: dict[str, int]) -> dict[str, int]:
            below: dict[str, int] = {}
            for sns, n in counts.items():
                seen, node = set(), sns
                while node in pairs and node not in seen:
                    seen.add(node)
                    below[node] = below.get(node, 0) + n
                    node = pairs[node]
            return below

        below, extras_below = up(count), up(extra_count)
        items = [
            FunctionalNode(
                sns=n.sns, name=n.name, level=n.level, description_pending=n.description_pending, child_count=c, row_count=count.get(n.sns, 0),
                rows_below=below.get(n.sns, 0), extra_count=extra_count.get(n.sns, 0), extras_below=extras_below.get(n.sns, 0),
            )
            for n, c in await tree_level(db, material.catalog_version_id, set(config), parent)
        ]
    level = FunctionalLevel(items=items)
    if parent is None:
        outside = [r for r in rows if r.sns not in config and (r.sns, r.co, r.al) != ROOT]
        if outside:
            ctx = await _context(db, material, user)
            level.outside = [_row_out(ctx, r) for r in _ordered(outside)]
    return level


@router.get("/rows", response_model=RowPage)
async def list_rows(
    page: int = Query(default=1, ge=1),
    page_size: int | None = Query(default=None, ge=1),
    sns: str | None = Query(default=None, max_length=40),
    q: str | None = Query(default=None, max_length=100),
    with_observations: bool | None = None,
    observation: str | None = Query(default=None, pattern=r"^[A-Z]{2}-\d{3}$"),
    severity: str | None = Query(default=None, pattern="^(bloqueante|aviso)$"),
    ct_sigle: str | None = Query(default=None, pattern="^[SN]$"),
    orphans: bool | None = None,
    mounted: bool | None = None,
    extra_sns: str | None = Query(default=None, min_length=6, max_length=6),
    multifunction: bool | None = None,
    incompatible: bool | None = None,
    access: MaterialAccess = Depends(require_material_permission(READ)),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> RowPage:
    params = await get_parameter(db, "confunfis")
    size = page_size or params["page_size"]
    if size > params["max_page_size"]:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=error_detail("page_size_too_large", max_page_size=params["max_page_size"]))
    ctx = await _context(db, access.material, user)
    rows = ctx.rows
    if sns:
        rows = [r for r in rows if r.sns.startswith(sns.strip().upper())]
    if q and q.strip():
        text = like_text(q.strip()).replace("\\", "").casefold()

        def hit(r: PhysicalPosition) -> bool:
            a = ctx.articles.get(r.article_id) if r.article_id else None
            haystack = [r.sns, r.article_name, r.function_text, a.noc if a else None, a.nombre if a else None] + ([x.pn for x in a.live_references] if a else [])
            return any(text in (h or "").casefold() for h in haystack)

        rows = [r for r in rows if hit(r)]
    if with_observations is not None:
        rows = [r for r in rows if bool(r.observation_codes) == with_observations]
    if observation:
        rows = [r for r in rows if observation in r.observation_codes]
    if severity:
        # The rows with a finding of that severity (E16: the rules' configuration).
        rules = await validation.settings(db)
        rows = [r for r in rows if any(validation.severity_of(rules.get(c), c) == severity for c in r.observation_codes if c in BY_CODE)]
    if ct_sigle:
        rows = [r for r in rows if r.ct_sigle == ct_sigle]
    if orphans is not None:
        rows = [r for r in rows if (str(r.id) in ctx.graph.orphan) == orphans]
    if mounted is not None:
        # Only the materials the user may open: the others stay unknown.
        rows = [r for r in rows if (r.id in ctx.mounted and ctx.mounted[r.id].id in ctx.visible) == mounted]
    if extra_sns:
        # E14: the rows whose extra function is this SNS (the functional view).
        holders = {e.position_id for e in ctx.extras if e.sns == extra_sns.upper()}
        rows = [r for r in rows if r.id in holders]
    if multifunction is not None:
        holders = {e.position_id for e in ctx.extras}
        rows = [r for r in rows if (r.id in holders) == multifunction]
    if incompatible is not None:
        named = {i for x in ctx.incompatibilities for i in (x.row_a_id, x.row_b_id)}
        rows = [r for r in rows if (r.id in named) == incompatible]
    rows = _ordered(rows)
    window = rows[(page - 1) * size : page * size]
    return RowPage(total=len(rows), page=page, page_size=size, items=[_row_out(ctx, r) for r in window])


async def _detail(db: AsyncSession, ctx: Context, row: PhysicalPosition) -> RowDetail:
    g = ctx.graph.rows[str(row.id)]
    by_id = {str(r.id): r for r in ctx.rows}
    cs = ctx.graph.parent.get(str(row.id))
    parents = [r for r in ctx.rows if cs is not None and (r.sns, r.co, r.al) == cs]
    children = [by_id[c.id] for c in ctx.graph.children.get(g.key, [])]
    history = (
        await db.execute(
            select(AuditLog, User.display_name).outerjoin(User, User.id == AuditLog.user_id)
            .where(AuditLog.entity_type == "physical_position", AuditLog.entity_id == str(row.id)).order_by(AuditLog.created_at.desc())
        )
    ).all()
    # E17: the authorization each change was made under, and the first reviewed baseline that includes it.
    reviewed = (await db.execute(
        select(Baseline.number, Baseline.created_at).where(Baseline.material_id == row.material_id, Baseline.state == "revisada").order_by(Baseline.created_at)
    )).all()

    def entry(a: AuditLog, name: str | None) -> dict[str, Any]:
        used = (a.after or {}).get("change_authorization") or []
        baseline = next((n for n, at in reviewed if at >= a.created_at), None)
        return {"id": str(a.id), "at": a.created_at.isoformat(), "action": a.action, "user": name,
                "authorization": used[0]["code"] if used else None, "baseline": baseline}

    return RowDetail(
        **_row_out(ctx, row).model_dump(),
        parents=[_row_out(ctx, r) for r in _ordered(parents)],
        children=[_row_out(ctx, r) for r in _ordered(children)],
        chains=[[ChainStep(qty=_plain(q), sns=s) for q, s in chain] for chain in ctx.graph.chains(g.hueco)],
        history=[entry(a, name) for a, name in history],
        hueco_als=sorted({r.al for r in ctx.rows if (r.sns, r.co) == (row.sns, row.co)}),
        extra_functions=[extra_out(ctx, e) for e in ctx.extras if e.position_id == row.id],
        incompatibilities=[incompatibility_out(ctx, i) for i in ctx.incompatibilities if row.id in (i.row_a_id, i.row_b_id)],
        parts=await cuf_parts(db, ctx, {row.article_id}) if row.article_id else [],
    )


def _path(ctx: Context, row: PhysicalPosition) -> list[PathStep] | None:
    """The rows from the CUF's (if any) down to `row`'s CS, taking the first
    row of each CS position; None for an orphan or a cycle."""
    by_key: dict[tuple[str, str, str], PhysicalPosition] = {}
    for r in _ordered(ctx.rows):
        by_key.setdefault((r.sns, r.co, r.al), r)
    steps: list[PathStep] = []
    seen: set[tuple[str, str, str]] = set()
    key = ctx.graph.parent.get(str(row.id))
    if str(row.id) in ctx.graph.orphan:
        return None
    while key is not None:
        if key in seen:
            return None
        seen.add(key)
        parent = by_key.get(key)
        if parent is None:  # the CUF without its own row
            break
        steps.append(PathStep(id=parent.id, position=key_text(key)))
        key = ctx.graph.parent.get(str(parent.id))
    return list(reversed(steps))


@router.get("/search", response_model=SearchResult)
async def search(
    q: str = Query(min_length=1, max_length=100),
    access: MaterialAccess = Depends(require_material_permission(READ)),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> SearchResult:
    """The physical tree's search (E14): by SNS, name, NOC or P/N; each hit
    with the path that opens the tree down to it, by position."""
    ctx = await _context(db, access.material, user)
    text = q.strip().casefold()

    def hit(r: PhysicalPosition) -> bool:
        a = ctx.articles.get(r.article_id) if r.article_id else None
        haystack = [r.sns, r.article_name, a.noc if a else None, a.nombre if a else None] + ([x.pn for x in a.live_references] if a else [])
        return any(text in (h or "").casefold() for h in haystack)

    hits = []
    for r in _ordered([r for r in ctx.rows if hit(r)]):
        path = _path(ctx, r)
        hits.append(SearchHit(row=_row_out(ctx, r), path=path or []))
    return SearchResult(total=len(hits), hits=hits)


@router.get("/rows/{row_id}", response_model=RowDetail)
async def get_row(
    row_id: uuid.UUID, access: MaterialAccess = Depends(require_material_permission(READ)), user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
) -> RowDetail:
    ctx = await _context(db, access.material, user)
    return await _detail(db, ctx, ctx.by_id(row_id))


@router.get("/next-slot", response_model=NextSlot)
async def next_slot(
    sns: str = Query(min_length=6, max_length=6), co: str | None = Query(default=None, pattern=r"^\d{2}$"),
    access: MaterialAccess = Depends(require_material_permission(READ)), db: AsyncSession = Depends(get_db),
) -> NextSlot:
    """The CO to suggest for a new row of `sns` (the next free one), or the
    AL for a new alternative of `sns` `co`."""
    params = await get_parameter(db, "confunfis")
    rows = [r for r in await confunfis.live_rows(db, access.material.id) if r.sns == sns.upper()]
    if co is None:
        used = {int(r.co) for r in rows if r.co.isdigit()}
        free = next((n for n in range(params["co"]["min"], params["co"]["max"] + 1) if n not in used), params["co"]["max"])
        return NextSlot(co=f"{free:02d}", al=f"{params['al']['min']:02d}")
    used_al = {int(r.al) for r in rows if r.co == co and r.al.isdigit()}
    free_al = next((n for n in range(max(1, params["al"]["min"]), params["al"]["max"] + 1) if n not in used_al), params["al"]["max"])
    return NextSlot(co=co, al=f"{free_al:02d}")


async def _serialized(db: AsyncSession, material: Material) -> None:
    """One change of a material's CONFUNFIS at a time: the observations of
    each see the rows of the previous one (a duplicate made by two people at
    once is still marked)."""
    await db.execute(select(Material.id).where(Material.id == material.id).with_for_update())


def _taken() -> HTTPException:
    """Another save created that NOC or P/N + NCAGE meanwhile."""
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_detail("article_identity_taken"))


def _invalid(exc: confunfis.RowError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=error_detail("confunfis_row_invalid", problems=exc.problems))


async def _done(db: AsyncSession, access: MaterialAccess, user: User, row_id: uuid.UUID) -> RowDetail:
    await confunfis.refresh_observations(db, access.material)
    await db.commit()
    ctx = await _context(db, access.material, user)
    return await _detail(db, ctx, ctx.by_id(row_id))


@router.post("/rows", response_model=RowDetail, status_code=status.HTTP_201_CREATED)
async def create_row(
    body: RowIn, request: Request, access: MaterialAccess = Depends(require_material_permission(EDIT)),
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
) -> RowDetail:
    await _serialized(db, access.material)
    values = body.model_dump(exclude=set(_IDENTITY))
    identity = {k: getattr(body, k) for k in _IDENTITY}
    try:
        row = await confunfis.save_row(db, access.material, values, user.id, source="manual", strict=True, identity=identity, audit_ip=client_ip(request))
    except confunfis.RowError as exc:
        raise _invalid(exc) from None
    except IntegrityError:
        raise _taken() from None
    return await _done(db, access, user, row.id)


async def _locked(db: AsyncSession, material: Material, row_id: uuid.UUID, version: int) -> PhysicalPosition:
    await _serialized(db, material)
    row = (
        await db.execute(
            select(PhysicalPosition).where(PhysicalPosition.id == row_id, PhysicalPosition.material_id == material.id, PhysicalPosition.deleted_at.is_(None)).with_for_update()
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_detail("confunfis_row_not_found"))
    if row.version != version:
        raise version_conflict(row.version)
    return row


def _values(row: PhysicalPosition) -> dict[str, Any]:
    return {name: getattr(row, name) for name in confunfis.FIELDS}


@router.patch("/rows/{row_id}", response_model=RowDetail)
async def update_row(
    row_id: uuid.UUID, body: RowUpdate, request: Request, access: MaterialAccess = Depends(require_material_permission(EDIT)),
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
) -> RowDetail:
    row = await _locked(db, access.material, row_id, body.version)
    sent = body.model_fields_set - {"version"}
    values = {**_values(row), **{k: getattr(body, k) for k in sent if k in confunfis.FIELDS}}
    changed = {k for k in sent if k in confunfis.FIELDS and getattr(body, k) != getattr(row, k)}
    checked = {"cs" if k.startswith("cs_") else k for k in changed}
    identity = {k: getattr(body, k) for k in _IDENTITY} if sent & set(_IDENTITY) else None
    try:
        await confunfis.save_row(
            db, access.material, values, user.id, source=row.source, strict=True, row=row, identity=identity, checked=checked, audit_ip=client_ip(request)
        )
    except confunfis.RowError as exc:
        raise _invalid(exc) from None
    except IntegrityError:
        raise _taken() from None
    return await _done(db, access, user, row.id)


@router.delete("/rows/{row_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_row(
    row_id: uuid.UUID, version: int, request: Request, confirm: bool = False, reset_al: bool = False,
    access: MaterialAccess = Depends(require_material_permission(EDIT)), user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
) -> None:
    """Removed logically (HR9); the rows hanging from it become orphans.
    `reset_al` (E14): when the hueco is left with a single AL, it goes back
    to AL 00 (NT §9.1.6) and the rows hanging from it follow."""
    if not confirm:
        raise confirmation_required()
    material = access.material
    row = await _locked(db, material, row_id, version)
    ip = client_ip(request)
    await confunfis.delete_row(db, material, row, user.id, ip)
    if reset_al:
        rows = await confunfis.live_rows(db, material.id)
        left = confunfis.single_al_left([r for r in rows if r.id != row.id], row.sns, row.co)
        if left is not None:
            confunfis.move_al(db, material, rows, row.sns, row.co, left, "00", user.id, ip)
    await confunfis.refresh_observations(db, material)
    await db.commit()


@router.post("/rows/{row_id}/reset-al", response_model=RowDetail)
async def reset_al(
    row_id: uuid.UUID, body: VersionIn, request: Request, access: MaterialAccess = Depends(require_material_permission(EDIT)),
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
) -> RowDetail:
    """"Volver a AL 00" (E14): an alternative alone in its hueco (OF-012)."""
    material = access.material
    row = await _locked(db, material, row_id, body.version)
    rows = await confunfis.live_rows(db, material.id)
    if (row.sns, row.co, row.al) == ROOT or confunfis.single_al_left(rows, row.sns, row.co) != row.al:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_detail("confunfis_not_single_alternative"))
    confunfis.move_al(db, material, rows, row.sns, row.co, row.al, "00", user.id, client_ip(request))
    return await _done(db, access, user, row.id)


def _copy(row: PhysicalPosition, user_id: uuid.UUID, **changes: Any) -> PhysicalPosition:
    return PhysicalPosition(
        id=uuid.uuid4(), material_id=row.material_id, source="manual", version=1, created_by=user_id, updated_by=user_id,
        article_id=row.article_id, article_reference_id=row.article_reference_id, link_notes=row.link_notes,
        **{**_values(row), **changes},
    )


@router.post("/rows/{row_id}/duplicate-alternative", response_model=RowDetail, status_code=status.HTTP_201_CREATED)
async def duplicate_alternative(
    row_id: uuid.UUID, body: VersionIn, request: Request, access: MaterialAccess = Depends(require_material_permission(EDIT)),
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
) -> RowDetail:
    """Same SNS + CO, the next free AL, the same QTY and CS. A row without
    alternatives (AL 00) becomes AL 01 first, and the rows hanging from it
    follow it; the copy takes the next one (02)."""
    material = access.material
    row = await _locked(db, material, row_id, body.version)
    params = await get_parameter(db, "confunfis")
    ip = client_ip(request)
    if (row.sns, row.co, row.al) == ROOT:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_detail("confunfis_root_has_no_alternative"))
    rows = await confunfis.live_rows(db, material.id)
    used = {int(r.al) for r in rows if (r.sns, r.co) == (row.sns, row.co) and r.al.isdigit()}
    free = [n for n in range(max(1, params["al"]["min"]), params["al"]["max"] + 1) if n not in used]
    if row.al == "00":
        if len(free) < 2:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_detail("confunfis_no_free_alternative"))
        confunfis.move_al(db, material, rows, row.sns, row.co, "00", f"{free.pop(0):02d}", user.id, ip)
    if not free:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_detail("confunfis_no_free_alternative"))
    copy = _copy(row, user.id, al=f"{free[0]:02d}")
    db.add(copy)
    await db.flush()
    audit.record(db, action="confunfis.row_created", entity_type="physical_position", entity_id=str(copy.id), user_id=user.id, material_id=material.id, after={**confunfis.snapshot(copy), "alternative_of": str(row.id)}, ip=ip)
    return await _done(db, access, user, copy.id)


@router.post("/rows/{row_id}/alternative-cs", response_model=RowDetail, status_code=status.HTTP_201_CREATED)
async def alternative_cs(
    row_id: uuid.UUID, body: AlternativeCsIn, request: Request, access: MaterialAccess = Depends(require_material_permission(EDIT)),
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
) -> RowDetail:
    """The same row under another CS (§9.1.8 case 2): only the CS changes."""
    row = await _locked(db, access.material, row_id, body.version)
    cs = (body.cs_sns.strip().upper(), body.cs_co.strip(), body.cs_al.strip())
    if not well_formed(*cs):
        raise _invalid(confunfis.RowError([{"field": "cs", "code": "cs_format", "params": {}}]))
    if cs == (row.cs_sns, row.cs_co, row.cs_al):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_detail("confunfis_same_cs"))
    copy = _copy(row, user.id, cs_sns=cs[0], cs_co=cs[1], cs_al=cs[2])
    db.add(copy)
    await db.flush()
    audit.record(
        db, action="confunfis.row_created", entity_type="physical_position", entity_id=str(copy.id), user_id=user.id, material_id=access.material.id,
        after={**confunfis.snapshot(copy), "cs_alternative_of": str(row.id)}, ip=client_ip(request),
    )
    return await _done(db, access, user, copy.id)
