"""The analysis of a CONFUNFIS book without writing (E16, fleco 1 of E15).

`Dry` is what the import's Runner (app/services/anexo_xi_import.py) writes
to when it analyses: the same pass, the same checks (`clean_values`,
`clean_product`, `clean_part`, `normalize_identity`) and the same way of
finding an article (NOC -> P/N + NCAGE -> exact name -> a provisional one),
over the records the CUF has, read once, and the ones the import would
create or change, kept here in memory. Nothing is added to the session and
no stored object is changed (a changed record is a copy): the analysis is a
read-only transaction (import_jobs: `read_only_analysis`) and locks nothing.

Then `context()` is the CUF as the import would leave it, for the
validator (app/validacion/engine.py): its findings, the provisional
articles, the new P/N + NCAGE.

What must hold: a line is new, modified, unchanged, removed or rejected here
exactly as when it is applied (the apply checks it: `_sheet_counts`).
"""

import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Article, ArticlePart, ArticleReference, ExtraFunction, FunctionalProduct, Incompatibility, Material, PhysicalPosition
from app.services import confunfis, cuf
from app.services import confunfis_extras as extras
from app.services.articles import Checker, autocorrect_article, data_of, normalize_identity
from app.services.parameters import get_parameter
from app.validacion import engine


def copy_of(obj: Any) -> SimpleNamespace:
    """A stored record as a plain object: changing it changes nothing stored."""
    return SimpleNamespace(**{c.key: getattr(obj, c.key) for c in obj.__mapper__.column_attrs})


def _new(model: Any, **values: Any) -> SimpleNamespace:
    out = SimpleNamespace(**{c.key: None for c in model.__mapper__.column_attrs})
    for name, value in values.items():
        setattr(out, name, value)
    return out


class Dry:
    def __init__(self, db: AsyncSession, material: Material):
        self.db, self.material = db, material
        # After every stored record: what the import creates is newer (the order of duplicates).
        self._clock = datetime.now(UTC).replace(microsecond=1)
        self.rows: dict[Any, Any] = {}
        self.products: dict[Any, Any] = {}
        self.extras: dict[Any, Any] = {}
        self.incompatibilities: dict[Any, Any] = {}
        # Parts: those of the parents the file brings (stored, changed, new), and the ones removed.
        self.parts: dict[Any, Any] = {}
        self.removed_parts: set[Any] = set()
        # The articles the import would create, and the P/N + NCAGE it would add.
        self.new_articles: dict[Any, Article] = {}
        self.new_references: list[SimpleNamespace] = []
        self._refs_of: dict[Any, list[SimpleNamespace]] = defaultdict(list)
        self._nameless: list[Article] | None = None
        self._checker: Checker | None = None
        self._config: set[str] | None = None
        self._criteria: dict[str, bool] | None = None

    def _now(self) -> datetime:
        self._clock += timedelta(microseconds=1)
        return self._clock

    async def load(self) -> None:
        mid = self.material.id
        self.rows = {r.id: r for r in sorted(await confunfis.live_rows(self.db, mid), key=lambda r: (r.created_at, str(r.id)))}
        self.products = {p.id: p for p in await extras.live_products(self.db, mid)}
        self.extras = {e.id: e for e in await extras.live_extras(self.db, mid)}
        self.incompatibilities = {i.id: i for i in await extras.live_incompatibilities(self.db, mid)}
        # Newer than anything stored (clock_timestamp on apply): even a record of this very second, or a database clock ahead.
        stored = [x.created_at for group in (self.rows, self.products, self.extras, self.incompatibilities) for x in group.values() if x.created_at]
        self._clock = max([self._clock, *stored])

    # ── the article master, read-only ────────────────────────────────────

    def live_refs(self, article: Article) -> list[Any]:
        own = list(article.live_references) if article.id not in self.new_articles else []
        return own + self._refs_of[article.id]

    async def _by_pn(self, pn: str, ncage: str | None) -> Article | None:
        query = (
            select(Article).join(ArticleReference, ArticleReference.article_id == Article.id)
            .where(ArticleReference.pn == pn, ArticleReference.deleted_at.is_(None), Article.deleted_at.is_(None))
        )
        query = query.where(ArticleReference.ncage == ncage) if ncage else query.where(ArticleReference.ncage.is_(None))
        found = (await self.db.execute(query.limit(1))).scalar_one_or_none()
        if found is not None:
            return found
        ref = next((r for r in self.new_references if (r.pn, r.ncage) == (pn, ncage)), None)
        return (self.new_articles.get(ref.article_id) or await self.db.get(Article, ref.article_id)) if ref else None

    async def find(self, noc: str | None, pn: str | None, ncage: str | None) -> Article | None:
        """`_find_article` over the master and what the import creates."""
        if noc:
            created = next((a for a in self.new_articles.values() if a.noc == noc), None)
            if created is not None:
                return created
            return (await self.db.execute(select(Article).where(Article.noc == noc, Article.deleted_at.is_(None)))).scalar_one_or_none()
        if pn:
            return await self._by_pn(pn, ncage)
        return None

    async def _by_name(self, name: str | None) -> Article | None:
        key = confunfis.name_key(name)
        if not key:
            return None
        if self._nameless is None:
            with_refs = select(ArticleReference.article_id).where(ArticleReference.deleted_at.is_(None))
            self._nameless = list((await self.db.execute(
                select(Article).where(Article.deleted_at.is_(None), Article.noc.is_(None), Article.id.not_in(with_refs)).order_by(Article.created_at)
            )).scalars())
        # The oldest first; one that gets a P/N here is no longer found by its name.
        for a in [*self._nameless, *self.new_articles.values()]:
            if a.noc is None and not self.live_refs(a) and confunfis.name_key(a.nombre) == key:
                return a
        return None

    async def _owner(self, pn: str, ncage: str | None, exclude: Any) -> bool:
        if not ncage:
            return False
        query = select(ArticleReference.article_id).join(Article, Article.id == ArticleReference.article_id).where(
            ArticleReference.pn == pn, ArticleReference.ncage == ncage, ArticleReference.deleted_at.is_(None), Article.deleted_at.is_(None),
            ArticleReference.article_id != exclude,
        )
        if (await self.db.execute(query.limit(1))).first() is not None:
            return True
        return any((r.pn, r.ncage) == (pn, ncage) and r.article_id != exclude for r in self.new_references)

    async def link(self, noc: str | None, pn: str | None, ncage: str | None, name: str | None) -> confunfis.Link:
        """`confunfis.link_article`, without writing."""
        if noc:
            article = await self.find(noc, None, None)
        elif pn:
            article = await self._by_pn(pn, ncage)
        else:
            article = await self._by_name(name)
        created = False
        if article is None:
            # Transient, never added to the session.
            article = Article(id=uuid.uuid4(), noc=noc, nombre=name or "", origen_nombre="coloquial", origin="confunfis", version=1, references=[], life_controls=[])
            autocorrect_article(article)
            if self._checker is None:
                self._checker = await Checker.load(self.db)
            self._checker.recheck(article)
            self.new_articles[article.id] = article
            created = True
        link = confunfis.Link(article=article, reference=None, created=created)
        if pn:
            own = next((r for r in self.live_refs(article) if (r.pn, r.ncage) == (pn, ncage)), None)
            if own is not None:
                link.reference = own
            elif await self._owner(pn, ncage, article.id):
                link.notes.append({"code": "pn_taken", "params": {"pn": pn, "ncage": ncage or ""}})
            else:
                principal = not any(r.principal for r in self.live_refs(article))
                ref = _new(ArticleReference, id=uuid.uuid4(), article_id=article.id, pn=pn, ncage=ncage, principal=principal, origin="confunfis", version=1)
                self.new_references.append(ref)
                self._refs_of[article.id].append(ref)
                link.reference = ref
        return link

    # ── CON_FUN_FIS ──────────────────────────────────────────────────────

    async def save_row(self, values: dict[str, Any], identity: dict[str, Any] | None, row: Any = None) -> None:
        """`confunfis.save_row(strict=False)`: the same RowError, nothing written."""
        bounds = (await get_parameter(self.db, "confunfis"))["qty"]
        clean, problems = confunfis.clean_values(values, strict=False, config=None, qty_bounds=bounds)
        link = None
        if identity is not None:
            noc, pn, ncage, wrong = normalize_identity(identity.get("noc"), identity.get("pn"), identity.get("ncage"))
            problems += [{"field": w, "code": f"{w}_invalid", "params": {}} for w in wrong]
            if ncage and not pn:
                problems.append({"field": "pn", "code": "pn_required", "params": {}})
            if problems:
                raise confunfis.RowError(problems)
            link = await self.link(noc, pn, ncage, clean["article_name"])
        elif problems:
            raise confunfis.RowError(problems)
        if row is None:
            out = _new(PhysicalPosition, id=uuid.uuid4(), material_id=self.material.id, source="import", version=1, created_at=self._now(), observations=[], observation_codes=[], link_notes=[])
        else:
            out = copy_of(row)
        for name, value in clean.items():
            setattr(out, name, value)
        if link is not None:
            out.article_id = link.article.id
            out.article_reference_id = link.reference.id if link.reference else None
            out.link_notes = link.notes
            if not out.article_name:
                out.article_name = link.article.nombre
        self.rows[out.id] = out

    def delete_row(self, row: Any) -> None:
        """With what hangs from it: what confunfis.ROW_REMOVAL_EXTENSIONS do on apply
        (E14 `_remove_with_row`; a test counts them, so a new one comes here too)."""
        self.rows.pop(row.id, None)
        for e in [e for e in self.extras.values() if e.position_id == row.id]:
            self.extras.pop(e.id)
        for i in [i for i in self.incompatibilities.values() if row.id in (i.row_a_id, i.row_b_id)]:
            self.incompatibilities.pop(i.id)

    def rows_by_key(self, key_of: Any) -> dict[tuple, Any]:
        out: dict[tuple, Any] = {}
        for r in sorted(self.rows.values(), key=lambda r: (r.created_at, str(r.id))):
            out.setdefault(key_of(r), r)
        return out

    # ── products ─────────────────────────────────────────────────────────

    async def save_product(self, values: dict[str, Any], product: Any = None) -> None:
        clean, problems = extras.clean_product(values, await get_parameter(self.db, "confunfis"))
        if problems:
            raise extras.ExtraError(problems)
        out = copy_of(product) if product is not None else _new(
            FunctionalProduct, id=uuid.uuid4(), material_id=self.material.id, source="import", version=1, created_at=self._now(), observations=[], observation_codes=[]
        )
        for name, value in clean.items():
            setattr(out, name, value)
        linked = await self.find(clean["noc"], None, None) if clean["noc"] else None
        out.article_id = linked.id if linked else None
        self.products[out.id] = out

    def remove_product(self, product: Any) -> None:
        self.products.pop(product.id, None)

    # ── parts ────────────────────────────────────────────────────────────

    async def live_parts(self, parent: Article) -> list[Any]:
        stored = [] if parent.id in self.new_articles else await extras.live_parts(self.db, parent.id)
        for p in stored:
            self.parts.setdefault(p.id, p)
        return stored

    async def save_part(self, parent: Article, values: dict[str, Any], identity: dict[str, Any] | None, part: Any = None) -> None:
        """`extras.save_part(strict=False)`: the same ExtraError, nothing written."""
        clean, problems = extras.clean_part(values, await get_parameter(self.db, "confunfis"), strict=False)
        link = None
        if identity is not None:
            noc, pn, ncage, wrong = normalize_identity(identity.get("noc"), identity.get("pn"), identity.get("ncage"))
            problems += [{"field": w, "code": f"{w}_invalid", "params": {}} for w in wrong]
            if ncage and not pn:
                problems.append({"field": "pn", "code": "pn_required", "params": {}})
            if not (noc or pn or clean["part_name"]):
                problems.append({"field": "part_name", "code": "part_identity_required", "params": {}})
            if problems:
                raise extras.ExtraError(problems)
            link = await self.link(noc, pn, ncage, clean["part_name"])
        elif problems:
            raise extras.ExtraError(problems)
        out = copy_of(part) if part is not None else _new(
            ArticlePart, id=uuid.uuid4(), parent_article_id=parent.id, source="import", version=1, created_at=self._now(), observations=[], observation_codes=[], link_notes=[]
        )
        for name, value in clean.items():
            setattr(out, name, value)
        if link is not None:
            out.part_article_id = link.article.id
            out.article_reference_id = link.reference.id if link.reference else None
            out.link_notes = list(link.notes)
            if not out.part_name:
                out.part_name = link.article.nombre
        self.parts[out.id] = out

    def remove_part(self, part: Any) -> None:
        self.parts.pop(part.id, None)
        self.removed_parts.add(part.id)

    # ── extra functions and incompatibilities ────────────────────────────

    async def check_extra(self, row: Any, sns: str, criterion: str, current: Any = None) -> list[dict[str, Any]]:
        """`extras.check_extra` over the extra functions as they would be."""
        if self._config is None:
            self._config = set(await cuf.normalized_config(self.db, self.material))
            self._criteria = await extras.codes_by_state(self.db, extras.CRITERIA_TABLE)
        problems: list[dict[str, Any]] = []
        if sns not in self._config:
            problems.append({"field": "sns", "code": "sns_not_in_config", "params": {"sns": sns}})
        elif sns == row.sns:
            problems.append({"field": "sns", "code": "sns_of_the_row", "params": {"sns": sns}})
        elif any(e.sns == sns and e.position_id == row.id and e.id != getattr(current, "id", None) for e in self.extras.values()):
            problems.append({"field": "sns", "code": "sns_repeated", "params": {"sns": sns}})
        if not (self._criteria or {}).get(criterion) and not (current is not None and current.criterion == criterion):
            problems.append({"field": "criterion", "code": "not_in_table", "params": {"table": extras.CRITERIA_TABLE}})
        return problems

    def add_extra(self, row: Any, sns: str, criterion: str, comment: str | None) -> None:
        out = _new(
            ExtraFunction, id=uuid.uuid4(), material_id=self.material.id, position_id=row.id, sns=sns, criterion=criterion,
            comment=(comment or "").strip() or None, source="import", version=1, created_at=self._now(),
        )
        self.extras[out.id] = out

    def change_extra(self, extra: Any, criterion: str, comment: str | None) -> None:
        out = copy_of(extra)
        out.criterion, out.comment = criterion, comment
        self.extras[out.id] = out

    def remove_extra(self, extra: Any) -> None:
        self.extras.pop(extra.id, None)

    def add_incompatibility(self, a: Any, b: Any, kind: str, reason: str) -> None:
        out = _new(
            Incompatibility, id=uuid.uuid4(), material_id=self.material.id, row_a_id=a.id, row_b_id=b.id, kind=kind, reason=reason,
            source="import", version=1, created_at=self._now(), observations=[], observation_codes=[],
        )
        self.incompatibilities[out.id] = out

    def change_incompatibility(self, item: Any, reason: str) -> None:
        out = copy_of(item)
        out.reason = reason
        self.incompatibilities[out.id] = out

    def remove_incompatibility(self, item: Any) -> None:
        self.incompatibilities.pop(item.id, None)

    # ── the result ───────────────────────────────────────────────────────

    async def context(self, parents: set[Any], file_cuf: dict[str, list[str]] | None) -> engine.Context:
        """The CUF as the import would leave it, for the validator; `parents`:
        the articles whose breakdown the file brings (their parts count too)."""
        db = self.db
        rows = sorted(self.rows.values(), key=lambda r: (r.created_at, str(r.id)))
        every = {p.id: p for p in await extras.live_parts(db)}
        for pid in self.removed_parts:
            every.pop(pid, None)
        every.update(self.parts)
        edges: dict[Any, set[Any]] = defaultdict(set)
        for p in every.values():
            if p.part_article_id:
                edges[p.parent_article_id].add(p.part_article_id)
        in_cuf = {r.article_id for r in rows if r.article_id}
        # The parts of the CUF's articles, as its validation counts them (app/services/validation.context).
        parts = [p for p in every.values() if p.parent_article_id in in_cuf]
        ids = in_cuf | {p.part_article_id for p in parts if p.part_article_id} | {p.parent_article_id for p in parts}
        stored_ids = ids - set(self.new_articles)
        articles: dict[Any, Article] = {a.id: a for a in (await db.execute(select(Article).where(Article.id.in_(stored_ids)))).scalars()} if stored_ids else {}
        articles.update({i: a for i, a in self.new_articles.items() if i in ids})
        ref_ids = {r.article_reference_id for r in rows if r.article_reference_id}
        references: dict[Any, Any] = {x.id: x for x in (await db.execute(select(ArticleReference).where(ArticleReference.id.in_(ref_ids)))).scalars()} if ref_ids else {}
        references.update({r.id: r for r in self.new_references if r.id in ref_ids})
        from app.services.validation import product_codes

        return engine.Context(
            rows=rows, config=set(await cuf.normalized_config(db, self.material)), params=await get_parameter(db, "confunfis"),
            articles=articles, references=references, article_findings={i: list(a.findings or []) for i, a in articles.items()},
            article_data={i: data_of(a) for i, a in articles.items()}, products=list(self.products.values()), parts=parts, part_edges=dict(edges),
            extras=list(self.extras.values()), incompatibilities=list(self.incompatibilities.values()), codes=await product_codes(db),
            mounted_sns=await confunfis.mounted_sns(db, self.material), file_cuf=file_cuf,
        )
