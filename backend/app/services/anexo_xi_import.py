"""The import of the CONFUNFIS book of a CUF (E15, NT 10/17 Anexo XI) over
the io_excel engine (analyze -> apply, import_job), one material at a time.

The book (app/services/anexo_xi_sheets.py): CON_FUN_FIS is required; TABLA
PRODUCTOS FUNCIONALES, TABLA DE PARTES and the Libro AAL's FUNCIONES
ADICIONALES and INCOMPATIBILIDADES are read when they are there; any other
sheet is listed and ignored. Row 2 is what identifies each sheet.

Two modes:
- merge ("Fusionar", the default): what is new is added, what changed is
  changed; nothing is removed (what the file does not have is kept, and
  counted unchanged, marked "not_in_file").
- replace ("Sustituir", the admin only, confirmed by typing the CUF's name):
  the result is exactly the file. The rows, products, extra functions and
  incompatibilities of the CUF the file does not have are removed (logically,
  audited); parts only for the articles whose breakdown the file brings
  (the parts are the article's, global: D16), and the extras only when the
  file has their sheet.

Matching (the diff): a row by SNS + CO + AL + CS (the CUF's own row with
its CS empty or 000000 01 00); a product by POL + N/A/E + supply unit; a
part by its parent article + COP + ALP. Records sharing a key (the demo's
duplicates) are matched in the order they appear.

The analysis writes everything with the services of E13/E14 (the link with
the master, the observations) in a transaction that is then rolled back:
so it reports what the result would be -- the observations, the provisional
articles and the new P/N + NCAGE, the parts that change articles other
CUF use -- with the same code that applies it. Applying runs it again,
for good, in one transaction (all or nothing), after checking that nothing
changed since the analysis (409 import_book_stale) and the confirmations: a
file whose CUF (NOC / P/N) is not the material's, and Sustituir. The audit
rows say the import job they came from.

IMPORT_GUARDS: checks before applying (E17: a CUF with a baseline will
need an authorized change). Each is awaited with (db, material, job) and
raises an HTTPException to refuse.
"""

import hashlib
import uuid
from collections import defaultdict
from collections.abc import Awaitable, Callable
from datetime import datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import error_detail
from app.io_excel.reader import Issue, Limits, ReadResult
from app.io_excel.targets import register
from app.io_excel.template import Template
from app.models import Article, ArticlePart, ArticleReference, ExtraFunction, FunctionalProduct, ImportJob, Incompatibility, Material, PhysicalPosition, User
from app.services import audit, confunfis, cuf
from app.services import confunfis_extras as extras
from app.services.anexo_xi_sheets import EXTRA_SHEET, INCOMPATIBILITY_SHEET, OFFICIAL, OWN, read_book
from app.services.articles import can_edit_articles, normalize_identity
from app.services.confunfis_graph import ROOT
from app.services.confunfis_sheet import IDENTITY_FIELDS, PARTS_SHEET, PRODUCTS_SHEET, ROW_FIELDS, SHEET, TEMPLATE
from app.services.parameters import get_parameter
from app.services.permissions import accessible_materials, material_access

ANEXO_XI = "confunfis_anexo_xi"
MERGE, REPLACE = "merge", "replace"
EDIT_PERMISSION = "confunfis.editar"
MODES = (MERGE, REPLACE)
ROW_COMPARED = ("qty", "noc", "pn", "ncage", "article_name", "function_text", "ct_sigle")
PRODUCT_COMPARED = ("designation", "noc", "quantity", "unit")

ImportGuard = Callable[[AsyncSession, Material, ImportJob], Awaitable[None]]
IMPORT_GUARDS: list[ImportGuard] = []


def _json(value: Any) -> Any:
    return str(value) if isinstance(value, Decimal) else value


def _pending(read: ReadResult | None) -> list[dict[str, Any]]:
    """A sheet's rows as the job keeps them (JSON: a QTY as text)."""
    if read is None:
        return []
    return [{"row": r.row, "values": {k: _json(v) for k, v in r.values.items()}, "issues": [i.as_json() for i in r.errors]} for r in read.rows]


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _same(a: Any, b: Any) -> bool:
    # A stored number (QTY, a product's quantity; the job keeps the file's as text) by value: 2 == "2.000000".
    # Two texts as text: the P/N "00123" is not "123".
    numbers = (Decimal, int, float)
    if (isinstance(a, numbers) or isinstance(b, numbers)) and not isinstance(a, bool) and not isinstance(b, bool) and a is not None and b is not None:
        try:
            return Decimal(str(a)) == Decimal(str(b))
        except ArithmeticError:
            return False
    return (_text(a) if isinstance(a, str) or a is None else a) == (_text(b) if isinstance(b, str) or b is None else b)


def _shown(value: Any) -> str:
    """A value as the report shows it: a quantity without its trailing zeros (2, not 2.000000)."""
    if value is None:
        return ""
    if isinstance(value, (Decimal, int, float)) or (isinstance(value, str) and value.replace(".", "", 1).replace("-", "", 1).isdigit()):
        number = Decimal(str(value))
        return str(number.to_integral_value() if number == number.to_integral_value() else number.normalize())
    return str(value)


def _row_key(values: dict[str, Any]) -> tuple:
    sns, co, al = _text(values.get("sns")), _text(values.get("co")), _text(values.get("al"))
    cs = (_text(values.get("cs_sns")), _text(values.get("cs_co")), _text(values.get("cs_al")))
    if (sns, co, al) == ROOT and cs == ROOT:
        cs = (None, None, None)  # the CUF's row: CS empty or 000000 01 00
    return (sns, co, al, *cs)


def _key_text(key: tuple) -> str:
    position = " ".join(x for x in key[:3] if x)
    cs = " ".join(x for x in key[3:] if x)
    return f"{position} ← {cs}" if cs else position


def _parse_position(sns: Any, co: Any, al: Any, cs: Any) -> tuple:
    parts = (_text(cs) or "").upper().split()
    cs3 = tuple(parts) if len(parts) == 3 else (None, None, None)
    return _row_key({"sns": sns, "co": co, "al": al, "cs_sns": cs3[0], "cs_co": cs3[1], "cs_al": cs3[2]})


def _grouped(items: list[Any], key: Callable[[Any], tuple]) -> dict[tuple, list[Any]]:
    out: dict[tuple, list[Any]] = defaultdict(list)
    for item in items:
        out[key(item)].append(item)
    return out


def _section() -> dict[str, Any]:
    return {"new": [], "modified": [], "unchanged": [], "removed": [], "rejected": []}


def _rejected(section: dict[str, Any], row: int, key: str, issues: list[dict[str, Any]]) -> None:
    section["rejected"].append({"row": row, "key": key, "issues": issues})


_HEADERS = {t.sheet: {c.field: c.headers[-1] for c in t.columns} for t in (*OFFICIAL, *OWN)}


def _header(sheet: str, field: str | None) -> str | None:
    """A field as the book's column calls it (QTY, NOMBRE…): what the user sees in the report."""
    if field is None:
        return None
    return _HEADERS.get(sheet, {}).get(field, field)


def _problem_issues(sheet: str, row: int, problems: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [Issue(p["code"], p.get("params", {}), row=row, header=_header(sheet, p.get("field"))).as_json() for p in problems]


async def _articles(db: AsyncSession, ids: set[Any]) -> dict[uuid.UUID, Article]:
    ids = {i for i in ids if i}
    return {a.id: a for a in (await db.execute(select(Article).where(Article.id.in_(ids)))).scalars()} if ids else {}


def _identity_of(article: Article | None, reference_id: uuid.UUID | None) -> tuple:
    if article is None:
        return (None, None, None)
    ref = next((r for r in article.live_references if r.id == reference_id), None)
    return (article.noc, ref.pn if ref else None, ref.ncage if ref else None)


async def _find_article(db: AsyncSession, noc: str | None, pn: str | None, ncage: str | None) -> Article | None:
    if noc:
        return (await db.execute(select(Article).where(Article.noc == noc, Article.deleted_at.is_(None)))).scalar_one_or_none()
    if pn:
        query = select(Article).join(ArticleReference, ArticleReference.article_id == Article.id).where(
            ArticleReference.pn == pn, ArticleReference.deleted_at.is_(None), Article.deleted_at.is_(None)
        )
        query = query.where(ArticleReference.ncage == ncage) if ncage else query.where(ArticleReference.ncage.is_(None))
        return (await db.execute(query.limit(1))).scalar_one_or_none()
    return None


class Runner:
    """One pass over the book: the diff, written with the E13/E14 services."""

    def __init__(self, db: AsyncSession, material: Material, mode: str, user: User | None, job_id: str | None, ip: str | None):
        self.db, self.material, self.mode, self.user, self.ip = db, material, mode, user, ip
        self.user_id = user.id if user else None
        self.job_id = job_id
        self.sheets: dict[str, dict[str, Any]] = {}
        self.part_parents: set[uuid.UUID] = set()
        # Each row's SNS CO AL ← CS, as it was before the run: how the report names what hangs from it.
        self.position_keys: dict[uuid.UUID, str] = {}

    # ── CON_FUN_FIS ──────────────────────────────────────────────────────

    async def rows(self, pending: list[dict[str, Any]]) -> None:
        section = self.sheets[SHEET] = _section()
        db, material = self.db, self.material
        stored = await confunfis.live_rows(db, material.id)
        articles = await _articles(db, {r.article_id for r in stored})
        by_key = _grouped(sorted(stored, key=lambda r: (r.created_at, str(r.id))), lambda r: _row_key({n: getattr(r, n) for n in ("sns", "co", "al", "cs_sns", "cs_co", "cs_al")}))
        matched: set[uuid.UUID] = set()
        for item in pending:
            values, row = item["values"], item["row"]
            key = _row_key(values)
            if item["issues"]:
                _rejected(section, row, _key_text(key), item["issues"])
                continue
            noc, pn, ncage, wrong = normalize_identity(values.get("noc"), values.get("pn"), values.get("ncage"))
            if wrong:
                _rejected(section, row, _key_text(key), [Issue(f"{w}_invalid", {"value": str(values.get(w))}, row=row).as_json() for w in wrong])
                continue
            fields = {k: values.get(k) for k in ROW_FIELDS}
            if (key[0], key[1], key[2]) == ROOT and key[3:] == (None, None, None):
                fields.update(cs_sns=None, cs_co=None, cs_al=None)
            candidates = [r for r in by_key.get(key, []) if r.id not in matched]
            match = candidates[0] if candidates else None
            try:
                if match is None:
                    await confunfis.save_row(db, material, fields, self.user_id, source="import", strict=False, identity={"noc": noc, "pn": pn, "ncage": ncage}, audit_ip=self.ip)
                    section["new"].append({"row": row, "key": _key_text(key), "values": {"name": _shown(values.get("article_name"))}})
                    continue
                matched.add(match.id)
                now = {**{n: getattr(match, n) for n in ("qty", "article_name", "function_text", "ct_sigle")},
                       **dict(zip(IDENTITY_FIELDS, _identity_of(articles.get(match.article_id), match.article_reference_id), strict=True))}
                incoming = {**{n: fields.get(n) for n in ("qty", "article_name", "function_text", "ct_sigle")}, "noc": noc, "pn": pn, "ncage": ncage}
                changes = [{"field": f, "header": _header(SHEET, f), "before": _shown(now[f]), "after": _shown(incoming[f])} for f in ROW_COMPARED if not _same(now[f], incoming[f])]
                if not changes:
                    section["unchanged"].append({"row": row, "key": _key_text(key), "values": {"name": _shown(match.article_name)}})
                    continue
                identity_changed = any(c["field"] in IDENTITY_FIELDS for c in changes)
                merged = {**{n: getattr(match, n) for n in confunfis.FIELDS}, **{k: v for k, v in fields.items() if k in confunfis.FIELDS}}
                await confunfis.save_row(
                    db, material, merged, self.user_id, source=match.source, strict=False, row=match,
                    identity={"noc": noc, "pn": pn, "ncage": ncage} if identity_changed else None, audit_ip=self.ip,
                )
                section["modified"].append({"row": row, "key": _key_text(key), "values": {"name": _shown(values.get("article_name") or match.article_name)}, "changes": changes})
            except confunfis.RowError as exc:
                _rejected(section, row, _key_text(key), _problem_issues(SHEET, row, exc.problems))
        for r in stored:
            if r.id in matched:
                continue
            key_text = _key_text(_row_key({n: getattr(r, n) for n in ("sns", "co", "al", "cs_sns", "cs_co", "cs_al")}))
            if self.mode == REPLACE:
                await confunfis.delete_row(db, material, r, self.user_id, self.ip)
                section["removed"].append({"row": None, "key": key_text, "values": {"name": _shown(r.article_name)}})
            else:
                # Fusionar keeps what the file does not have: unchanged.
                section["unchanged"].append({"row": None, "key": key_text, "values": {"name": _shown(r.article_name)}, "not_in_file": True})
        await db.flush()

    # ── TABLA PRODUCTOS FUNCIONALES ──────────────────────────────────────

    async def products(self, pending: list[dict[str, Any]]) -> None:
        section = self.sheets[PRODUCTS_SHEET] = _section()
        db, material = self.db, self.material
        params = await get_parameter(db, "confunfis")
        stored = await extras.live_products(db, material.id)
        by_key = _grouped(sorted(stored, key=lambda p: (p.created_at, str(p.id))), lambda p: (p.pol_code, p.nae, p.supply_unit))
        matched: set[uuid.UUID] = set()
        for item in pending:
            values, row = item["values"], item["row"]
            clean, problems = extras.clean_product(values, params)
            key = (clean["pol_code"], clean["nae"], clean["supply_unit"])
            key_text = " · ".join(x or "—" for x in key)
            if item["issues"] or problems:
                _rejected(section, row, key_text, item["issues"] + _problem_issues(PRODUCTS_SHEET, row, problems))
                continue
            candidates = [p for p in by_key.get(key, []) if p.id not in matched]
            match = candidates[0] if candidates else None
            if match is None:
                await extras.save_product(db, material, values, self.user_id, source="import", ip=self.ip)
                section["new"].append({"row": row, "key": key_text, "values": {"name": clean["designation"] or ""}})
                continue
            matched.add(match.id)
            changes = [
                {"field": f, "header": _header(PRODUCTS_SHEET, f), "before": _shown(getattr(match, f)), "after": _shown(clean[f])}
                for f in PRODUCT_COMPARED if not _same(getattr(match, f), clean[f])
            ]
            if not changes:
                section["unchanged"].append({"row": row, "key": key_text})
                continue
            await extras.save_product(db, material, values, self.user_id, source=match.source, product=match, ip=self.ip)
            section["modified"].append({"row": row, "key": key_text, "changes": changes})
        for p in stored:
            if p.id in matched:
                continue
            key_text = " · ".join(x or "—" for x in (p.pol_code, p.nae, p.supply_unit))
            if self.mode == REPLACE:
                await extras.remove_product(db, material, p, self.user_id, self.ip)
                section["removed"].append({"row": None, "key": key_text, "values": {"name": p.designation}})
            else:
                section["unchanged"].append({"row": None, "key": key_text, "not_in_file": True})
        await extras.refresh_products(db, material)

    # ── TABLA DE PARTES ──────────────────────────────────────────────────

    async def parts(self, pending: list[dict[str, Any]]) -> None:
        section = self.sheets[PARTS_SHEET] = _section()
        db = self.db
        matched: set[uuid.UUID] = set()
        stored_by_parent: dict[uuid.UUID, list[ArticlePart]] = {}
        for item in pending:
            values, row = item["values"], item["row"]
            pnoc, ppn, pncage, pwrong = normalize_identity(values.get("parent_noc"), values.get("parent_pn"), values.get("parent_ncage"))
            noc, pn, ncage, wrong = normalize_identity(values.get("noc"), values.get("pn"), values.get("ncage"))
            key_text = f"{pnoc or ppn or ''} · {_shown(values.get('cop'))}/{_shown(values.get('alp'))}"
            if item["issues"] or pwrong or wrong:
                bad = [Issue(f"{w}_invalid", {"value": ""}, row=row).as_json() for w in (*pwrong, *wrong)]
                _rejected(section, row, key_text, item["issues"] + bad)
                continue
            parent = await _find_article(db, pnoc, ppn, pncage)
            if parent is None:
                _rejected(section, row, key_text, [Issue("part_parent_not_found", {"value": pnoc or ppn or ""}, row=row).as_json()])
                continue
            self.part_parents.add(parent.id)
            if parent.id not in stored_by_parent:
                stored_by_parent[parent.id] = sorted(await extras.live_parts(db, parent.id), key=lambda p: (p.created_at, str(p.id)))
            key_text = f"{parent.noc or parent.nombre} · {_shown(values.get('cop'))}/{_shown(values.get('alp'))}"
            cop, alp = _text(values.get("cop")), _text(values.get("alp")) or "00"
            candidates = [p for p in stored_by_parent[parent.id] if (p.cop, p.alp) == (cop, alp) and p.id not in matched]
            match = candidates[0] if candidates else None
            fields = {"cop": cop, "alp": alp, "quantity": values.get("quantity"), "part_name": None}
            try:
                if match is None:
                    await extras.save_part(db, parent, fields, self.user_id, source="import", strict=False, identity={"noc": noc, "pn": pn, "ncage": ncage}, ip=self.ip)
                    section["new"].append({"row": row, "key": key_text, "values": {"name": noc or pn or ""}, "parent": str(parent.id)})
                    continue
                matched.add(match.id)
                part_article = (await _articles(db, {match.part_article_id})).get(match.part_article_id) if match.part_article_id else None
                now = dict(zip(IDENTITY_FIELDS, _identity_of(part_article, match.article_reference_id), strict=True))
                changes = [{"field": f, "header": _header(PARTS_SHEET, f), "before": _shown(now[f]), "after": _shown(v)} for f, v in (("noc", noc), ("pn", pn), ("ncage", ncage)) if not _same(now[f], v)]
                if not _same(match.quantity, values.get("quantity")):
                    changes.append({"field": "quantity", "header": "quantity", "before": _shown(match.quantity), "after": _shown(values.get("quantity"))})
                if not changes:
                    section["unchanged"].append({"row": row, "key": key_text})
                    continue
                identity_changed = any(c["field"] in IDENTITY_FIELDS for c in changes)
                await extras.save_part(
                    db, parent, {**fields, "part_name": match.part_name}, self.user_id, source=match.source, strict=False, part=match,
                    identity={"noc": noc, "pn": pn, "ncage": ncage} if identity_changed else None, ip=self.ip,
                )
                section["modified"].append({"row": row, "key": key_text, "changes": changes, "parent": str(parent.id)})
            except extras.ExtraError as exc:
                _rejected(section, row, key_text, _problem_issues(PARTS_SHEET, row, exc.problems))
        # Only the breakdowns the file brings: the parts are the article's.
        for parent_id, parts in stored_by_parent.items():
            for p in parts:
                if p.id in matched:
                    continue
                if self.mode == REPLACE:
                    await extras.remove_part(db, p, self.user_id, self.ip)
                    section["removed"].append({"row": None, "key": f"{p.cop}/{p.alp}", "values": {"name": p.part_name or ""}, "parent": str(parent_id)})
                else:
                    section["unchanged"].append({"row": None, "key": f"{p.cop}/{p.alp}", "not_in_file": True})
        await extras.refresh_parts(db, self.part_parents)

    # ── the Libro AAL's own sheets ───────────────────────────────────────

    async def _rows_by_key(self) -> dict[tuple, PhysicalPosition]:
        out: dict[tuple, PhysicalPosition] = {}
        for r in sorted(await confunfis.live_rows(self.db, self.material.id), key=lambda r: (r.created_at, str(r.id))):
            out.setdefault(_row_key({n: getattr(r, n) for n in ("sns", "co", "al", "cs_sns", "cs_co", "cs_al")}), r)
        return out

    async def extra_functions(self, pending: list[dict[str, Any]]) -> None:
        section = self.sheets[EXTRA_SHEET] = _section()
        db, material = self.db, self.material
        rows = await self._rows_by_key()
        stored = await extras.live_extras(db, material.id)
        matched: set[uuid.UUID] = set()
        for item in pending:
            values, row = item["values"], item["row"]
            key = _parse_position(values.get("sns"), values.get("co"), values.get("al"), values.get("cs"))
            sns = (_text(values.get("sns_extra")) or "").upper()
            key_text = f"{_key_text(key)} + {sns}"
            position = rows.get(key)
            if item["issues"] or position is None:
                _rejected(section, row, key_text, item["issues"] or [Issue("row_not_in_book", {"value": _key_text(key)}, row=row).as_json()])
                continue
            criterion, comment = _text(values.get("criterion")) or "", _text(values.get("comment"))
            match = next((e for e in stored if e.position_id == position.id and e.sns == sns and e.id not in matched), None)
            if match is None:
                problems = await extras.check_extra(db, material, position, sns, criterion)
                if problems:
                    _rejected(section, row, key_text, _problem_issues(EXTRA_SHEET, row, problems))
                    continue
                await extras.add_extra(db, material, position, sns, criterion, comment, self.user_id, source="import", ip=self.ip)
                section["new"].append({"row": row, "key": key_text, "values": {"name": criterion}})
                continue
            matched.add(match.id)
            changes = [{"field": f, "header": _header(EXTRA_SHEET, f), "before": _shown(getattr(match, f)), "after": _shown(v)} for f, v in (("criterion", criterion), ("comment", comment)) if not _same(getattr(match, f), v)]
            if not changes:
                section["unchanged"].append({"row": row, "key": key_text})
                continue
            problems = await extras.check_extra(db, material, position, sns, criterion, current=match)
            if problems:
                _rejected(section, row, key_text, _problem_issues(EXTRA_SHEET, row, problems))
                continue
            before = extras.extra_snapshot(match)
            match.criterion, match.comment, match.version, match.updated_by = criterion, comment, match.version + 1, self.user_id
            audit.record(db, action="confunfis.extra_function_updated", entity_type="extra_function", entity_id=str(match.id), user_id=self.user_id, material_id=material.id, before=before, after=extras.extra_snapshot(match), ip=self.ip)
            section["modified"].append({"row": row, "key": key_text, "changes": changes})
        for e in stored:
            if e.id in matched:
                continue
            if self.mode == REPLACE:
                await extras.remove_extra(db, material, e, self.user_id, self.ip)
                section["removed"].append({"row": None, "key": self._extra_key(e), "values": {"name": e.criterion}})
            else:
                section["unchanged"].append({"row": None, "key": self._extra_key(e), "not_in_file": True})

    async def incompatibilities(self, pending: list[dict[str, Any]]) -> None:
        section = self.sheets[INCOMPATIBILITY_SHEET] = _section()
        db, material = self.db, self.material
        rows = await self._rows_by_key()
        stored = await extras.live_incompatibilities(db, material.id)
        matched: set[uuid.UUID] = set()
        for item in pending:
            values, row = item["values"], item["row"]
            ka = _parse_position(values.get("a_sns"), values.get("a_co"), values.get("a_al"), values.get("a_cs"))
            kb = _parse_position(values.get("b_sns"), values.get("b_co"), values.get("b_al"), values.get("b_cs"))
            kind = (_text(values.get("kind")) or "").lower()
            key_text = f"{_key_text(ka)} {kind} {_key_text(kb)}"
            a, b = rows.get(ka), rows.get(kb)
            reason = _text(values.get("reason"))
            issues = list(item["issues"])
            if a is None or b is None:
                issues.append(Issue("row_not_in_book", {"value": _key_text(ka if a is None else kb)}, row=row).as_json())
            elif a.id == b.id:
                issues.append(Issue("same_row", {}, row=row).as_json())
            if kind not in ("excluye", "requiere"):
                issues.append(Issue("incompatibility_kind_invalid", {"value": kind}, row=row).as_json())
            if not reason:
                issues.append(Issue("required", {}, row=row, header="MOTIVO").as_json())
            if issues:
                _rejected(section, row, key_text, issues)
                continue
            match = next((i for i in stored if extras.same_incompatibility(i, a.id, b.id, kind) and i.id not in matched), None)
            if match is None:
                await extras.add_incompatibility(db, material, a, b, kind, reason, self.user_id, source="import", ip=self.ip)
                section["new"].append({"row": row, "key": key_text, "values": {"name": reason}})
                continue
            matched.add(match.id)
            if _same(match.reason, reason):
                section["unchanged"].append({"row": row, "key": key_text})
                continue
            before, old_reason = extras.incompatibility_snapshot(match), match.reason
            match.reason, match.version, match.updated_by = reason, match.version + 1, self.user_id
            audit.record(db, action="confunfis.incompatibility_updated", entity_type="incompatibility", entity_id=str(match.id), user_id=self.user_id, material_id=material.id, before=before, after=extras.incompatibility_snapshot(match), ip=self.ip)
            section["modified"].append({"row": row, "key": key_text, "changes": [{"field": "reason", "header": _header(INCOMPATIBILITY_SHEET, "reason"), "before": old_reason, "after": reason}]})
        for i in stored:
            if i.id in matched:
                continue
            if self.mode == REPLACE:
                await extras.remove_incompatibility(db, material, i, self.user_id, self.ip)
                section["removed"].append({"row": None, "key": self._incompatibility_key(i), "values": {"name": i.reason}})
            else:
                section["unchanged"].append({"row": None, "key": self._incompatibility_key(i), "not_in_file": True})

    def _extra_key(self, e: ExtraFunction) -> str:
        return f"{self.position_keys.get(e.position_id, '?')} · {e.sns}"

    def _incompatibility_key(self, i: Incompatibility) -> str:
        return f"{self.position_keys.get(i.row_a_id, '?')} {i.kind} {self.position_keys.get(i.row_b_id, '?')}"

    async def run(self, pending: dict[str, list[dict[str, Any]]]) -> None:
        db, mid = self.db, self.material.id
        self.position_keys = {
            r.id: _key_text(_row_key({n: getattr(r, n) for n in ("sns", "co", "al", "cs_sns", "cs_co", "cs_al")})) for r in await confunfis.live_rows(db, mid)
        }
        extras_before, incompatibilities_before = await extras.live_extras(db, mid), await extras.live_incompatibilities(db, mid)
        await self.rows(pending[SHEET])
        # Sustituir: a row removed takes its extra functions and incompatibilities with it
        # (ROW_REMOVAL_EXTENSIONS); they are removed too, and the report must say so.
        alive_e = {e.id for e in await extras.live_extras(db, mid)}
        alive_i = {i.id for i in await extras.live_incompatibilities(db, mid)}
        cascaded = {
            EXTRA_SHEET: [{"row": None, "key": self._extra_key(e), "values": {"name": e.criterion}, "with_row": True} for e in extras_before if e.id not in alive_e],
            INCOMPATIBILITY_SHEET: [{"row": None, "key": self._incompatibility_key(i), "values": {"name": i.reason}, "with_row": True} for i in incompatibilities_before if i.id not in alive_i],
        }
        if PRODUCTS_SHEET in pending:
            await self.products(pending[PRODUCTS_SHEET])
        if PARTS_SHEET in pending:
            await self.parts(pending[PARTS_SHEET])
        if EXTRA_SHEET in pending:
            await self.extra_functions(pending[EXTRA_SHEET])
        if INCOMPATIBILITY_SHEET in pending:
            await self.incompatibilities(pending[INCOMPATIBILITY_SHEET])
        for sheet, items in cascaded.items():
            if items:
                self.sheets.setdefault(sheet, _section())["removed"].extend(items)
        await confunfis.refresh_observations(self.db, self.material)


def _sheet_counts(sheets: dict[str, Any]) -> dict[str, dict[str, int]]:
    return {name: {k: len(v) for k, v in section.items()} for name, section in sheets.items()}


async def fingerprint(db: AsyncSession, material: Material, parents: set[uuid.UUID]) -> str:
    """What the analysis saw: every record it may change, by id and version."""
    parts: list[tuple] = []
    for model in (PhysicalPosition, FunctionalProduct, ExtraFunction, Incompatibility):
        parts += sorted((str(i), v) for i, v in (await db.execute(select(model.id, model.version).where(model.material_id == material.id, model.deleted_at.is_(None)))).all())
    if parents:
        parts += sorted((str(i), v) for i, v in (await db.execute(select(ArticlePart.id, ArticlePart.version).where(ArticlePart.parent_article_id.in_(parents), ArticlePart.deleted_at.is_(None)))).all())
    # What the comparison reads too: the articles the rows point to (their NOC, P/N and NCAGE)
    # and the CUF's identity (whether the file's CUF is another).
    used = select(PhysicalPosition.article_id).where(PhysicalPosition.material_id == material.id, PhysicalPosition.deleted_at.is_(None))
    parts += sorted((str(i), v) for i, v in (await db.execute(select(Article.id, Article.version).where(Article.id.in_(used)))).all())
    parts += sorted((str(i), v) for i, v in (await db.execute(select(ArticleReference.id, ArticleReference.version).where(ArticleReference.article_id.in_(used), ArticleReference.deleted_at.is_(None)))).all())
    parts.append(("material", material.noc, material.part_number))
    return hashlib.sha256(repr(parts).encode()).hexdigest()


def _cuf_of(pending: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """The CUF the file says (its rows' and products' CUF columns)."""
    nocs, pns = set(), set()
    for item in pending.get(SHEET, []):
        nocs.add(_text(item["values"].get("cuf_noc")))
        pns.add(_text(item["values"].get("cuf_pn")))
    for item in pending.get(PRODUCTS_SHEET, []):
        nocs.add(_text(item["values"].get("cuf_noc")))
        pns.add(_text(item["values"].get("cuf_pn")))
    return {"noc": sorted(n for n in nocs if n), "pn": sorted(p for p in pns if p)}


async def _material(db: AsyncSession, params: dict[str, Any]) -> Material:
    material = await db.get(Material, uuid.UUID(params["material_id"]))
    if material is None or material.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_detail("material_not_found"))
    return material


class AnexoXiTarget:
    kind = ANEXO_XI

    def can_import(self, user: User, params: dict[str, Any]) -> bool:
        # The material's permission is the route's (confunfis.editar); Sustituir, the admin's.
        return user.is_admin or params.get("mode") == MERGE

    async def template(self, db: AsyncSession, params: dict[str, Any]) -> Template:
        return TEMPLATE

    async def stored(self, db: AsyncSession, params: dict[str, Any], template: Template) -> dict:
        return {}

    def read_file(self, template: Template, data: bytes, limits: Limits) -> ReadResult:
        return read_book(template, data, limits)

    async def analyze(self, db: AsyncSession, params: dict[str, Any], template: Template, read: ReadResult) -> dict[str, Any]:
        material = await _material(db, params)
        errors = [i.as_json() for i in read.errors]
        for name, sheet in read.sheets.items():
            errors += [{**i.as_json(), "sheet": name} for i in sheet.errors]
        # The CUF named in "global parts" are only those the importer may open.
        viewer = await db.get(User, uuid.UUID(params["user_id"])) if params.get("user_id") else None
        parts_sheet = read.sheets.get(PARTS_SHEET)
        if parts_sheet is not None and parts_sheet.rows and not (viewer and await can_edit_articles(db, viewer)):
            # The parts are the article's (global, E14): the route's articulos.editar, not only confunfis.editar.
            errors.append({**Issue("parts_need_article_permission", {}).as_json(), "sheet": PARTS_SHEET})
        pending = {SHEET: _pending(read)}
        for name, sheet in read.sheets.items():
            if not sheet.errors:
                pending[name] = _pending(sheet)
        report: dict[str, Any] = {
            "columns": [{"field": "key", "header": "SNS CO AL"}], "template_fields": [c.field for c in template.columns],
            "new": [], "modified": [], "unchanged": [], "errors": errors,
            "warnings": [i.as_json() for i in read.warnings] + [{**i.as_json(), "sheet": n} for n, s in read.sheets.items() for i in s.warnings],
            "ignored_sheets": read.ignored_sheets, "mode": params.get("mode", MERGE), "notices": [],
        }
        if errors:
            report["sheets"] = {}
            report["counts"] = {"rows": len(read.rows), "new": 0, "modified": 0, "unchanged": 0, "removed": 0, "rejected": 0, "errors": len(errors), "warnings": len(report["warnings"])}
            return report
        file_cuf = _cuf_of(pending)
        differs = bool(
            (file_cuf["noc"] and file_cuf["noc"] != [material.noc]) or (file_cuf["pn"] and file_cuf["pn"] != [material.part_number])
        )
        report["cuf"] = {"file": file_cuf, "material": {"noc": material.noc, "pn": material.part_number, "name": material.name}, "differs": differs}
        if differs:
            report["notices"].append({"code": "cuf_differs"})
        if not await cuf.subcategory_codes(db, material.id):
            # Every row would be outside the CUF's configuration (E16).
            report["notices"].append({"code": "no_subcategories"})
        report["pending"] = pending
        # The dry run: everything written, measured, then rolled back by the engine.
        # now() is the transaction's start: what the dry run creates has it, what was there is older.
        started = (await db.execute(select(func.now()))).scalar_one()
        runner = Runner(db, material, params.get("mode", MERGE), None, None, None)
        parents = await self._parents(db, pending)
        report["fingerprint"] = await fingerprint(db, material, parents)
        await runner.run(pending)
        await db.flush()
        report["sheets"] = runner.sheets
        report["result"] = await self._result(db, material, started, runner, viewer)
        top = runner.sheets[SHEET]
        report["new"], report["modified"], report["unchanged"], report["removed"], report["rejected"] = (
            top["new"], top["modified"], top["unchanged"], top["removed"], top["rejected"],
        )
        total = lambda k: sum(len(s[k]) for s in runner.sheets.values())  # noqa: E731
        report["counts"] = {
            "rows": len(read.rows), "new": total("new"), "modified": total("modified"), "unchanged": total("unchanged"),
            "removed": total("removed"), "rejected": total("rejected"), "errors": 0, "warnings": len(report["warnings"]),
            "cuf_differs": int(differs),
            **{f"{part}_{k}": len(runner.sheets[sheet][k]) for part, sheet in (("rows", SHEET), ("products", PRODUCTS_SHEET), ("parts", PARTS_SHEET), ("extras", EXTRA_SHEET), ("incompatibilities", INCOMPATIBILITY_SHEET)) if sheet in runner.sheets for k in ("new", "modified", "unchanged", "removed", "rejected")},
        }
        return report

    async def _parents(self, db: AsyncSession, pending: dict[str, list[dict[str, Any]]]) -> set[uuid.UUID]:
        out: set[uuid.UUID] = set()
        for item in pending.get(PARTS_SHEET, []):
            noc, pn, ncage, _w = normalize_identity(item["values"].get("parent_noc"), item["values"].get("parent_pn"), item["values"].get("parent_ncage"))
            parent = await _find_article(db, noc, pn, ncage)
            if parent is not None:
                out.add(parent.id)
        return out

    async def _result(
        self, db: AsyncSession, material: Material, started: datetime, runner: Runner, viewer: User | None,
    ) -> dict[str, Any]:
        """What the result would have: observations, provisional articles,
        new P/N + NCAGE, and the parts that change articles other CUF use."""
        rows = await confunfis.live_rows(db, material.id)
        observations: dict[str, int] = defaultdict(int)
        for r in rows:
            for code in r.observation_codes:
                observations[code] += 1
        for p in await extras.live_products(db, material.id):
            for code in p.observation_codes:
                observations[code] += 1
        for i in await extras.live_incompatibilities(db, material.id):
            for code in i.observation_codes:
                observations[code] += 1
        for p in await extras.live_parts(db):
            if p.parent_article_id in runner.part_parents:
                for code in p.observation_codes:
                    observations[code] += 1
        new_articles = (await db.execute(select(Article).where(Article.created_at >= started))).scalars().all()
        new_refs = (await db.execute(select(ArticleReference).where(ArticleReference.created_at >= started))).scalars().all()
        names = {a.id: a for a in await _articles(db, {r.article_id for r in new_refs})}
        changed_parents = {uuid.UUID(x["parent"]) for k in ("new", "modified", "removed") for x in runner.sheets.get(PARTS_SHEET, {}).get(k, [])}
        global_parts = []
        if changed_parents:
            users = (
                await db.execute(
                    select(PhysicalPosition.article_id, Material.id, Material.name).join(Material, Material.id == PhysicalPosition.material_id)
                    .where(PhysicalPosition.article_id.in_(changed_parents), PhysicalPosition.deleted_at.is_(None), Material.deleted_at.is_(None), Material.id != material.id)
                    .distinct()
                )
            ).all()
            visible = {a.material.id for a in await accessible_materials(db, viewer)} if viewer else set()
            parents = await _articles(db, changed_parents)
            by_parent: dict[uuid.UUID, list[str]] = defaultdict(list)
            hidden: dict[uuid.UUID, int] = defaultdict(int)
            for article_id, mid, name in users:
                if mid in visible:
                    by_parent[article_id].append(name)
                else:
                    hidden[article_id] += 1
            global_parts = [
                {"article": parents[a].nombre, "noc": parents[a].noc, "materials": sorted(by_parent[a]), "others": hidden[a]}
                for a in sorted(changed_parents, key=lambda a: parents[a].nombre) if by_parent[a] or hidden[a]
            ]
        return {
            "observations": dict(sorted(observations.items())),
            "provisional_articles": [{"noc": a.noc, "name": a.nombre} for a in new_articles if a.origin == "confunfis"],
            "new_references": [{"pn": r.pn, "ncage": r.ncage, "article": names[r.article_id].nombre if r.article_id in names else ""} for r in new_refs],
            "global_parts": global_parts,
        }

    async def apply(self, db: AsyncSession, job: ImportJob, template: Template, user: User, ip: str | None) -> None:
        material = await _material(db, job.params)
        report = job.report
        mode = job.params.get("mode", MERGE)
        if report.get("cuf", {}).get("differs") and not job.params.get("confirm_cuf"):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_detail("import_cuf_not_confirmed"))
        if mode == REPLACE and job.counts.get("rejected"):
            # A rejected line still names a record: replacing would remove the record it was meant to keep.
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_detail("import_replace_has_rejected"))
        if mode == REPLACE and job.params.get("confirm_name") != material.name:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_detail("import_replace_not_confirmed"))
        # The permissions again: they may have changed since the upload.
        access = await material_access(db, user, material.id)
        if access is None or not access.can(EDIT_PERMISSION):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_detail("permission_denied", permission=EDIT_PERMISSION))
        pending = report["pending"]
        if pending.get(PARTS_SHEET) and not await can_edit_articles(db, user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_detail("permission_denied", permission="articulos.editar"))
        for guard in IMPORT_GUARDS:
            await guard(db, material, job)
        await db.execute(select(Material.id).where(Material.id == material.id).with_for_update())
        parents = await self._parents(db, pending)
        if parents:
            # The parts are global: another CUF's import may touch the same parents.
            await db.execute(select(Article.id).where(Article.id.in_(parents)).order_by(Article.id).with_for_update())
        if await fingerprint(db, material, parents) != report.get("fingerprint"):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_detail("import_book_stale"))
        runner = Runner(db, material, mode, user, str(job.id), ip)
        source = {"import_job": str(job.id), "file_name": job.file_name}
        # Every audit row of this import says where it came from.
        with audit.origin(source):
            await runner.run(pending)
            await db.flush()
        # What was written must be what the user saw (HR7): the master may have changed since
        # (a P/N now taken, an article with that NOC), which the fingerprint does not cover.
        if _sheet_counts(runner.sheets) != _sheet_counts(report.get("sheets", {})):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_detail("import_book_stale"))
        audit.record(db, action="confunfis.book_imported", entity_type="material", entity_id=str(material.id), user_id=user.id, material_id=material.id, after={**source, "mode": mode, "counts": job.counts}, ip=ip)


register(AnexoXiTarget())

