"""The Fichero Carga of SIGLE and the "Maestro AAL" (E12): import (over
the io_excel engine, analyze -> apply) and export of the articles.

- FICHERO_CARGA: sheet "Artículo", two header rows (the names and the
  PRISMA codes, row 2 is what identifies the file), the 30 fields in the
  official order, data from row 3. It has no P/N nor NCAGE.
- MAESTRO: the same sheet with columns added on the right: P/N, NCAGE (the
  principal reference, E13), the name's origin and the life controls 2 and
  3. Imported with the same key. Its export adds the sheet "Referencias"
  with every reference of every article (the principal one marked); the
  import (E15) reads it too, when it is there: a P/N + NCAGE an article
  does not have yet is added (with the origin the row says), one it has is
  unchanged, one of another article is rejected. The principal is the one
  of the "Artículo" sheet (a "Principal" that says otherwise is a notice);
  a reference missing from the sheet is never removed. Exporting and
  importing again changes nothing; importing and exporting again gives the
  same sheet.

The columns come from article_field_definition (header, PRISMA code, type,
length, decimals): nothing of a field is written here.

Key of a row: its NOC (normalized as E10/E11: upper case, no spaces); a
row without one is matched with the article of the same P/N + NCAGE (the
Maestro has them) or, failing that, with the article without NOC nor P/N
of exactly the same name (case and repeated spaces aside); otherwise it is
a new, provisional article. The P/N + NCAGE is any of the article's
references (E13): a row with another of its references makes that one the
principal.

The analysis reports new, modified (field by field), unchanged, rejected
rows (a NOC or NCAGE badly formed, a value that cannot be stored: never
cut, HR6) with their row and reason, the AR findings by rule and the AR-008
corrections. Rejected rows do not block applying (they are listed, HR7);
an error of the file itself (its sheet, its headers) does. Applying never
deletes an article that is not in the file.
"""

import re
import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import error_detail
from app.io_excel.cells import display, from_json, to_json
from app.io_excel.reader import Issue, Limits, ReadResult, read_rows, sheet_names
from app.io_excel.targets import register
from app.io_excel.template import Column, ColumnType, Template
from app.models import FIELD_COLUMNS, MAX_LIFE_CONTROLS, NAME_ORIGINS, REFERENCE_ORIGINS, Article, ArticleReference, ImportJob, User
from app.models.article import LIFE_CODE_FIELD, LIFE_QUANTITY_FIELD
from app.services import audit, confunfis
from app.services.article_fields import FieldDef, field_defs
from app.services.articles import PN_MAX_LENGTH, Checker, data_of, life_of, normalize_identity, reference_owner, set_data, set_life, set_principal, snapshot
from app.validacion.articulos import RULES, LifeControl, autocorrect

FICHERO_CARGA, MAESTRO = "articles_fichero_carga", "articles_maestro"
SHEET = "Artículo"
NOC_FIELD, NAME_FIELD = "cdART", "NomArt"
# The Maestro AAL's own columns: (field, name, code). The life controls
# after the first take the Fichero Carga's codes with their position.
_PN, _NCAGE, _ORIGIN = "pn", "ncage", "origen_nombre"


def _extra_life(position: int) -> tuple[str, str]:
    return f"{LIFE_CODE_FIELD}{position}", f"{LIFE_QUANTITY_FIELD}{position}"


def build_template(defs: dict[str, FieldDef], kind: str) -> Template:
    columns: list[Column] = []
    for d in defs.values():
        if d.prisma == NOC_FIELD:
            # Read as written: the spaces go and the format is checked after
            # (normalize_identity), so a NOC with spaces is not "too long".
            columns.append(Column(d.prisma, (d.header, d.prisma), upper=True, key=True, width=16))
        else:
            columns.append(d.as_column(headers=(d.header, d.prisma)))
    if kind == MAESTRO:
        code, quantity = defs[LIFE_CODE_FIELD], defs[LIFE_QUANTITY_FIELD]
        columns += [
            Column(_PN, ("P/N", "PN"), max_length=PN_MAX_LENGTH, width=18),
            Column(_NCAGE, ("NCAGE", "NCAGE"), upper=True, width=10),
            Column(_ORIGIN, ("Origen del nombre", "OrigenNombre"), choices=tuple((o, o) for o in NAME_ORIGINS), width=14),
        ]
        for position in range(2, MAX_LIFE_CONTROLS + 1):
            code_field, quantity_field = _extra_life(position)
            columns += [
                code.as_column(field=code_field, headers=(f"{code.header} {position}", code_field)),
                quantity.as_column(field=quantity_field, headers=(f"{quantity.header} {position}", quantity_field)),
            ]
    return Template(
        code=kind, sheet=SHEET, columns=tuple(columns), header_rows=2, checked_header_rows=(2,), header_look="fichero_carga",
    )


REFERENCES_SHEET = "Referencias"


def references_template() -> Template:
    """The Maestro AAL's second sheet (export only): every reference."""
    return Template(
        code="articles_references", sheet=REFERENCES_SHEET, unique_keys=False,
        columns=(
            Column(NOC_FIELD, ("NOC del artículo",), width=16),
            Column(NAME_FIELD, ("Nombre del artículo",), width=40),
            Column(_PN, ("P/N",), max_length=PN_MAX_LENGTH, key=True, width=18),
            Column(_NCAGE, ("NCAGE",), width=10),
            Column("principal", ("Principal",), ColumnType.YES_NO, width=10),
            Column("origin", ("Origen",), choices=tuple((o, o) for o in REFERENCE_ORIGINS), width=14),
        ),
    )


def reference_rows(articles: list[Article]) -> list[dict[str, Any]]:
    return [
        {NOC_FIELD: a.noc, NAME_FIELD: a.nombre, _PN: r.pn, _NCAGE: r.ncage, "principal": r.principal, "origin": r.origin}
        for a in articles
        for r in a.live_references
    ]


def _name_key(name: str | None) -> str:
    return re.sub(r"\s+", " ", name or "").strip().casefold()


def export_values(article: Article, kind: str) -> dict[str, Any]:
    """An article as a row of the template."""
    life = life_of(article)
    values: dict[str, Any] = dict(data_of(article))
    if life:
        values[LIFE_CODE_FIELD], values[LIFE_QUANTITY_FIELD] = life[0].unit_code, life[0].quantity
    if kind == MAESTRO:
        values.update({_PN: article.pn, _NCAGE: article.ncage, _ORIGIN: article.origen_nombre})
        for position, c in enumerate(life[1:], start=2):
            code_field, quantity_field = _extra_life(position)
            values[code_field], values[quantity_field] = c.unit_code, c.quantity
    return values


def _life_from(values: dict[str, Any], kind: str, stored: list[LifeControl] | None) -> list[LifeControl]:
    first = LifeControl(values.get(LIFE_CODE_FIELD), values.get(LIFE_QUANTITY_FIELD))
    if kind == MAESTRO:
        rest = [LifeControl(values.get(_extra_life(p)[0]), values.get(_extra_life(p)[1])) for p in range(2, MAX_LIFE_CONTROLS + 1)]
    else:
        # The Fichero Carga only has the first pair: the others are kept.
        rest = (stored or [])[1:]
    return [first, *rest]


def _key_text(noc: str | None, pn: str | None, ncage: str | None, name: str | None) -> str:
    return noc or (f"{pn} / {ncage}" if pn and ncage else name or "")


async def _live_articles(db: AsyncSession) -> list[Article]:
    return list((await db.execute(select(Article).where(Article.deleted_at.is_(None)))).scalars())


class ArticleTarget:
    """One of the two templates (`kind`)."""

    def __init__(self, kind: str):
        self.kind = kind

    def can_import(self, user: User, params: dict[str, Any]) -> bool:
        return user.is_admin

    async def template(self, db: AsyncSession, params: dict[str, Any]) -> Template:
        return build_template(await field_defs(db), self.kind)

    def read_file(self, template: Template, data: bytes, limits: Limits) -> ReadResult:
        """The "Artículo" sheet and, in the Maestro AAL, "Referencias" if it is there (E15)."""
        read = read_rows(template, data, limits)
        if self.kind == MAESTRO and REFERENCES_SHEET in sheet_names(data):
            read.sheets[REFERENCES_SHEET] = read_rows(references_template(), data, limits)
        return read

    async def stored(self, db: AsyncSession, params: dict[str, Any], template: Template) -> dict:
        return {}

    async def analyze(self, db: AsyncSession, params: dict[str, Any], template: Template, read: ReadResult) -> dict[str, Any]:
        checker = await Checker.load(db)
        by_field = {c.field: c for c in template.columns}
        articles = await _live_articles(db)
        by_noc = {a.noc: a for a in articles if a.noc}
        by_pn = {(r.pn, r.ncage): a for a in articles for r in a.live_references if r.ncage}
        by_name = {_name_key(a.nombre): a for a in articles if not a.noc and not a.live_references}
        report: dict[str, Any] = {
            "columns": [{"field": f, "header": by_field[f].headers[0]} for f in (NOC_FIELD, NAME_FIELD)],
            "template_fields": [c.field for c in template.columns],
            "new": [], "modified": [], "unchanged": [], "rejected": [],
            "errors": [i.as_json() for i in read.errors],
            "warnings": [i.as_json() for i in read.warnings],
            "ar": {code: [] for code in RULES if code != "AR-008"},
            "corrections": [],
            "pending": {"new": [], "modified": []},
        }
        seen: dict[str, int] = {}
        seen_pn: dict[tuple[str, str], int] = {}
        for row in read.rows:
            values = row.values
            noc, pn, ncage, wrong = normalize_identity(values.get(NOC_FIELD), values.get(_PN), values.get(_NCAGE))
            name = values.get(NAME_FIELD)
            issues = [i.as_json() for i in row.errors]
            for which, field in (("noc", NOC_FIELD), ("ncage", _NCAGE)):
                if which in wrong:
                    issues.append(Issue(f"{which}_invalid", {"value": str(values.get(field))}, row=row.row, header=by_field[field].title).as_json())
            if not name:
                issues.append(Issue("name_required", {}, row=row.row, header=by_field[NAME_FIELD].title).as_json())
            if ncage and not pn:
                issues.append(Issue("pn_required", {}, row=row.row, header=by_field[_PN].title).as_json())
            key = _key_text(noc, pn, ncage, name)
            identity = f"noc:{noc}" if noc else f"pn:{pn}/{ncage}" if pn and ncage else f"name:{_name_key(name)}"
            if not issues and identity in seen:
                issues.append(Issue("duplicate_article", {"first_row": seen[identity]}, row=row.row).as_json())
            match = by_noc.get(noc) if noc else (by_pn.get((pn, ncage)) if pn and ncage else None) or by_name.get(_name_key(name))
            if not issues and pn and ncage:
                # P/N + NCAGE is unique too: in the file and against the stored articles.
                if (pn, ncage) in seen_pn:
                    issues.append(Issue("duplicate_pn_ncage", {"first_row": seen_pn[(pn, ncage)]}, row=row.row).as_json())
                elif (other := by_pn.get((pn, ncage))) is not None and other is not match:
                    issues.append(Issue("pn_ncage_taken", {"value": f"{pn} / {ncage}"}, row=row.row).as_json())
            if issues:
                report["rejected"].append({"row": row.row, "key": key, "issues": issues})
                continue
            seen[identity] = row.row
            if pn and ncage:
                seen_pn[(pn, ncage)] = row.row
            report["warnings"] += [i.as_json() for i in row.warnings]
            data = {p: values.get(p) for p in FIELD_COLUMNS}
            data[NOC_FIELD] = noc
            corrections = autocorrect(data)
            report["corrections"] += [{"row": row.row, "key": key, **c} for c in corrections]
            life = _life_from(values, self.kind, life_of(match) if match else None)
            # An empty origin is the default one, as apply writes it.
            identity_values = {"pn": pn, "ncage": ncage, "origen_nombre": values.get(_ORIGIN) or "coloquial"} if self.kind == MAESTRO else {}
            for f in checker.findings(data, life):
                report["ar"][f["code"]].append({"row": row.row, "key": key, "name": name, "field": f["field"], "problem": f["problem"], "params": f["params"]})
            file_values = {**data, **self._life_values(life), **identity_values}
            as_json = {f: to_json(by_field[f], v) for f, v in file_values.items() if f in by_field}
            if match is None:
                report["new"].append({"row": row.row, "key": key, "values": {NOC_FIELD: noc or "", NAME_FIELD: name}})
                report["pending"]["new"].append({"row": row.row, "values": as_json})
                continue
            stored_values = export_values(match, self.kind)
            stored_values[NOC_FIELD] = match.noc
            changes = [
                {"field": f, "header": f"{by_field[f].headers[0]} ({by_field[f].title})", "before": display(by_field[f], stored_values.get(f)), "after": display(by_field[f], v)}
                for f, v in file_values.items()
                if f in by_field and stored_values.get(f) != v and not (f == NOC_FIELD and v is None)
            ]
            if not changes:
                report["unchanged"].append({"row": row.row, "key": key})
                continue
            report["modified"].append({"row": row.row, "key": key, "changes": changes})
            report["pending"]["modified"].append({"row": row.row, "ref": str(match.id), "version": match.version, "values": as_json})
        if REFERENCES_SHEET in read.sheets:
            self._analyze_references(report, read.sheets[REFERENCES_SHEET], articles, read)
        ar_counts = {f"ar_{code[-3:]}": len({i["row"] for i in items}) for code, items in report["ar"].items()}
        report["counts"] = {
            "rows": len(read.rows),
            "new": len(report["new"]),
            "modified": len(report["modified"]),
            "unchanged": len(report["unchanged"]),
            "rejected": len(report["rejected"]),
            "errors": len(report["errors"]),
            "rows_with_errors": 0,
            "warnings": len(report["warnings"]),
            "corrections": len(report["corrections"]),
            "references_new": len(report.get("references", {}).get("new", [])),
            "references_unchanged": report.get("references", {}).get("unchanged", 0),
            "references_rejected": len(report.get("references", {}).get("rejected", [])),
            **ar_counts,
        }
        return report

    def _analyze_references(self, report: dict[str, Any], sheet: ReadResult, articles: list[Article], read: ReadResult) -> None:
        """The "Referencias" sheet: what it adds to each article (E15)."""
        section: dict[str, Any] = {"new": [], "unchanged": 0, "rejected": [], "notices": []}
        report["references"] = section
        for issue in sheet.errors:
            report["errors"].append({**issue.as_json(), "sheet": REFERENCES_SHEET})
        if sheet.errors:
            return
        by_noc = {a.noc: a for a in articles if a.noc}
        by_name = {_name_key(a.nombre): a for a in articles if not a.noc}
        owner = {(r.pn, r.ncage): a for a in articles for r in a.live_references}
        # The articles the "Artículo" sheet creates, and the principal each will have.
        principal: dict[str, tuple[str | None, str | None]] = {}
        coming: set[str] = set()
        for row in read.rows:
            noc, pn, ncage, _wrong = normalize_identity(row.values.get(NOC_FIELD), row.values.get(_PN), row.values.get(_NCAGE))
            who = f"noc:{noc}" if noc else f"name:{_name_key(row.values.get(NAME_FIELD))}"
            principal[who] = (pn, ncage)
            coming.add(who)
        seen: dict[tuple[str, str | None], int] = {}
        for row in sheet.rows:
            values = row.values
            noc, pn, ncage, wrong = normalize_identity(values.get(NOC_FIELD), values.get(_PN), values.get(_NCAGE))
            name = values.get(NAME_FIELD)
            issues = [i.as_json() for i in row.errors] + [Issue(f"{w}_invalid", {"value": str(values.get(w if w != "noc" else NOC_FIELD))}, row=row.row).as_json() for w in wrong]
            who = f"noc:{noc}" if noc else f"name:{_name_key(name)}"
            article = by_noc.get(noc) if noc else by_name.get(_name_key(name))
            if not pn:
                issues.append(Issue("pn_required", {}, row=row.row).as_json())
            elif article is None and who not in coming:
                issues.append(Issue("reference_article_not_found", {"value": noc or name or ""}, row=row.row).as_json())
            elif (other := owner.get((pn, ncage))) is not None and other is not article:
                issues.append(Issue("pn_ncage_taken", {"value": f"{pn} / {ncage or ''}"}, row=row.row).as_json())
            elif (pn, ncage) in seen:
                issues.append(Issue("duplicate_pn_ncage", {"first_row": seen[(pn, ncage)]}, row=row.row).as_json())
            key = f"{pn} / {ncage or ''}"
            if issues:
                section["rejected"].append({"row": row.row, "key": key, "issues": issues})
                continue
            seen[(pn, ncage)] = row.row
            will_be_principal = principal.get(who, (article.pn, article.ncage) if article else (None, None)) == (pn, ncage)
            if bool(values.get("principal")) != will_be_principal:
                section["notices"].append({"row": row.row, "key": key, "code": "reference_principal_from_article_sheet"})
            if will_be_principal or (article is not None and owner.get((pn, ncage)) is article):
                # It has it already (or the "Artículo" sheet gives it, as its principal).
                section["unchanged"] += 1
                continue
            origin = values.get("origin") if values.get("origin") in REFERENCE_ORIGINS else "importacion"
            section["new"].append({
                "row": row.row, "key": key, "article": (article.nombre if article else name) or "",
                "noc": noc, "name": name, "pn": pn, "ncage": ncage, "origin": origin,
            })
        report["warnings"] += [i.as_json() for r in sheet.rows for i in r.warnings]

    def _life_values(self, life: list[LifeControl]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for position, c in enumerate(life, start=1):
            if position == 1:
                out[LIFE_CODE_FIELD], out[LIFE_QUANTITY_FIELD] = c.unit_code, c.quantity
            elif self.kind == MAESTRO:
                code_field, quantity_field = _extra_life(position)
                out[code_field], out[quantity_field] = c.unit_code, c.quantity
        return out

    def _decoded(self, template: Template, values: dict[str, Any]) -> tuple[dict[str, Any], list[LifeControl], dict[str, Any]]:
        by_field = {c.field: c for c in template.columns}
        decoded = {f: from_json(by_field[f], v) for f, v in values.items()}
        data = {p: decoded.get(p) for p in FIELD_COLUMNS}
        life = [LifeControl(decoded.get(LIFE_CODE_FIELD), decoded.get(LIFE_QUANTITY_FIELD))]
        identity: dict[str, Any] = {}
        if self.kind == MAESTRO:
            life += [LifeControl(decoded.get(_extra_life(p)[0]), decoded.get(_extra_life(p)[1])) for p in range(2, MAX_LIFE_CONTROLS + 1)]
            identity = {"pn": decoded.get(_PN), "ncage": decoded.get(_NCAGE), "origen_nombre": decoded.get(_ORIGIN) or "coloquial"}
        return data, life, identity

    async def _check_pn_free(self, db: AsyncSession, identity: dict[str, Any], article_id: uuid.UUID | None, row: int) -> None:
        """Another article took this P/N + NCAGE after the analysis: stale."""
        pn, ncage = identity.get("pn"), identity.get("ncage")
        if pn and await reference_owner(db, pn, ncage, exclude=article_id):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_detail("import_stale", row=row))

    async def _set_identity(self, db: AsyncSession, article: Article, identity: dict[str, Any], user_id: uuid.UUID | None) -> None:
        if not identity:
            return
        article.origen_nombre = identity["origen_nombre"]
        await set_principal(db, article, identity["pn"], identity["ncage"], user_id, "importacion")

    async def apply(self, db: AsyncSession, job: ImportJob, template: Template, user: User, ip: str | None) -> None:
        await self.apply_report(db, job.report, template, user.id, {"import_job": str(job.id), "file_name": job.file_name}, ip)

    async def apply_report(
        self, db: AsyncSession, report: dict[str, Any], template: Template, user_id: uuid.UUID | None, source: dict[str, Any], ip: str | None
    ) -> None:
        """Writes what an analysis found (also scripts/seed_demo_articles.py,
        without a user)."""
        checker = await Checker.load(db)
        touched: set[uuid.UUID] = set()
        corrections: dict[int, list[dict[str, Any]]] = {}
        for c in report.get("corrections", []):
            corrections.setdefault(c["row"], []).append({"code": c["code"], "field": c["field"], "value": c["value"]})
        for item in report["pending"]["modified"]:
            article = (await db.execute(select(Article).where(Article.id == uuid.UUID(item["ref"])).with_for_update())).scalar_one_or_none()
            if article is None or article.deleted_at is not None or article.version != item["version"]:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_detail("import_stale", row=item["row"]))
            before = snapshot(article)
            data, life, identity = self._decoded(template, item["values"])
            await self._check_pn_free(db, identity, article.id, item["row"])
            if data[NOC_FIELD] is None:
                data[NOC_FIELD] = article.noc  # matched by its P/N or name: it keeps its NOC
            set_data(article, data)
            if self.kind == FICHERO_CARGA:
                life = [life[0], *life_of(article)[1:]]
            set_life(article, life)
            await self._set_identity(db, article, identity, user_id)
            checker.recheck(article)
            article.version += 1
            article.updated_by = user_id
            audit.record(
                db, action="article.updated", entity_type="article", entity_id=str(article.id), user_id=user_id,
                before=before, after={**snapshot(article), **source, "corrections": corrections.get(item["row"], [])}, ip=ip,
            )
            touched.add(article.id)
        for item in report["pending"]["new"]:
            data, life, identity = self._decoded(template, item["values"])
            noc = data[NOC_FIELD]
            if noc and (await db.execute(select(Article.id).where(Article.noc == noc, Article.deleted_at.is_(None)))).first():
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_detail("import_stale", row=item["row"]))
            await self._check_pn_free(db, identity, None, item["row"])
            article = Article(id=uuid.uuid4(), version=1, created_by=user_id, updated_by=user_id, origen_nombre="coloquial", nombre=data[NAME_FIELD], references=[], life_controls=[])
            set_data(article, data)
            set_life(article, life)
            checker.recheck(article)
            db.add(article)
            await self._set_identity(db, article, identity, user_id)
            await db.flush()
            audit.record(
                db, action="article.created", entity_type="article", entity_id=str(article.id), user_id=user_id,
                after={**snapshot(article), **source, "corrections": corrections.get(item["row"], [])}, ip=ip,
            )
        touched |= await self._apply_references(db, report.get("references", {}).get("new", []), user_id, source, ip)
        # The CONFUNFIS rows of the changed articles (their name, NOC, P/N: E13).
        await confunfis.refresh_materials(db, article_ids=touched)

    async def _apply_references(
        self, db: AsyncSession, items: list[dict[str, Any]], user_id: uuid.UUID | None, source: dict[str, Any], ip: str | None
    ) -> set[uuid.UUID]:
        """The references the "Referencias" sheet adds, after the articles (a new one may own them)."""
        touched: set[uuid.UUID] = set()
        for item in items:
            if item["noc"]:
                article = (await db.execute(select(Article).where(Article.noc == item["noc"], Article.deleted_at.is_(None)).with_for_update())).scalar_one_or_none()
            else:
                candidates = (await db.execute(select(Article).where(Article.noc.is_(None), Article.deleted_at.is_(None)))).scalars()
                article = next((a for a in candidates if _name_key(a.nombre) == _name_key(item["name"])), None)
            if article is None or await reference_owner(db, item["pn"], item["ncage"], exclude=article.id):
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_detail("import_stale", row=item["row"]))
            if any((r.pn, r.ncage) == (item["pn"], item["ncage"]) for r in article.live_references):
                continue
            reference = ArticleReference(
                id=uuid.uuid4(), pn=item["pn"], ncage=item["ncage"], principal=article.principal_reference is None, origin=item["origin"],
                version=1, created_by=user_id, updated_by=user_id,
            )
            article.references.append(reference)
            article.version += 1
            article.updated_by = user_id
            await db.flush()
            audit.record(
                db, action="article.reference_added", entity_type="article", entity_id=str(article.id), user_id=user_id,
                after={"reference": {"id": str(reference.id), "pn": reference.pn, "ncage": reference.ncage, "principal": reference.principal, "origin": reference.origin}, **source},
                ip=ip,
            )
            touched.add(article.id)
        return touched


register(ArticleTarget(FICHERO_CARGA))
register(ArticleTarget(MAESTRO))
