"""The CONFUNFIS book of a CUF (E15, NT 10/17 Anexo XI) as an Excel file:

- ANEXO: the three sheets of the official format -- CON_FUN_FIS, TABLA
  PRODUCTOS FUNCIONALES and TABLA DE PARTES -- with the block headers of row
  1 merged, CO / AL / COP / ALP and every code as text, QTY and quantities
  as numbers, the root row 000000 with its CS empty and the rows in tree
  order (SNS, CO, AL, CS). The parts are those of the articles in the CUF's
  CONFUNFIS. A product in bulk (no quantity) is written "N/A", as the NT's
  kerosene.
- AAL: the same three and the book's own two (documented in
  app/services/anexo_xi_sheets.py): FUNCIONES ADICIONALES and
  INCOMPATIBILIDADES, each row naming its CONFUNFIS rows by SNS + CO + AL +
  CS.
- PLANTILLA: the empty book for a subcontractor: the three sheets with their
  headers, the CUF's columns and the root row filled, the help sheets SNS
  PERMITIDOS (the CUF's normalized configuration) and TABLAS (D155, POL,
  NAE, UNIDAD_MEDIDA_PF), and Excel lists on CT SIGLE, N/A/E, the supply
  unit and the SNS (when the configuration fits a list).

The block headers follow the demo book (demo/CONFUNFIS_DEMO_TRAMONTANA.xlsx)
so that importing it and exporting again gives the same cells.
"""

import io
import uuid
from decimal import Decimal
from typing import Any

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.io_excel.writer import excel_text
from app.models import Article, Material, PhysicalPosition, ReferenceValue, SnsPosition
from app.services import confunfis, cuf, validation_report
from app.services import confunfis_extras as extras
from app.services.anexo_xi_sheets import EXTRA_SHEET, INCOMPATIBILITY_SHEET, SHEETS, SheetSpec
from app.services.confunfis_graph import ROOT
from app.services.parameters import get_parameter

ANEXO, AAL, PLANTILLA = "anexo", "aal", "plantilla"
SNS_SHEET, TABLES_SHEET = "SNS PERMITIDOS", "TABLAS"
HELP_SHEETS = (SNS_SHEET, TABLES_SHEET)
HELP_TABLES = ("D155", "POL", "NAE", extras.UNIT_TABLE)
# Excel's list validation takes a range; a configuration of more SNS than
# this is left without it (the help sheet still lists them).

_FONT = Font(bold=True)
_FILL = PatternFill("solid", fgColor="DDE3F0")
_CENTER = Alignment(horizontal="center", vertical="center")


def _plain(value: Decimal | None) -> Any:
    """A quantity as a number: 1, not 1.000000."""
    if value is None:
        return None
    return int(value) if value == value.to_integral_value() else float(value)


def _cell(ws, row: int, col: int, value: Any, text: bool) -> None:
    cell = ws.cell(row=row, column=col)
    if text:
        cell.number_format = "@"
    if value is None:
        return
    if text or isinstance(value, str):
        # Always text, as io_excel/writer.py: openpyxl would take a string
        # starting with "=" (a name typed in the app or a subcontractor's
        # cell) as a live formula.
        cell.value = excel_text(str(value))
        cell.data_type = "s"
    else:
        cell.value = value


def _sheet(book, spec: SheetSpec, rows: list[list[Any]]):
    ws = book.create_sheet(spec.name)
    for first, last, title in spec.blocks:
        ws.cell(row=1, column=first, value=title)
        if last > first:
            ws.merge_cells(start_row=1, start_column=first, end_row=1, end_column=last)
    for i, column in enumerate(spec.columns, start=1):
        ws.cell(row=2, column=i, value=column.header)
        ws.column_dimensions[get_column_letter(i)].width = column.width
        for r in (1, 2):
            c = ws.cell(row=r, column=i)
            c.font, c.fill = _FONT, _FILL
            if r == 1:
                c.alignment = _CENTER
    for r, values in enumerate(rows, start=3):
        for i, (column, value) in enumerate(zip(spec.columns, values, strict=True), start=1):
            _cell(ws, r, i, value, column.text)
    ws.freeze_panes = "A3"
    return ws


def _cuf_columns(material: Material) -> list[Any]:
    return [material.noc, material.name, material.part_number, material.ncage]


async def _articles(db: AsyncSession, ids: set[uuid.UUID | None]) -> dict[uuid.UUID, Article]:
    ids = {i for i in ids if i}
    return {a.id: a for a in (await db.execute(select(Article).where(Article.id.in_(ids)))).scalars()} if ids else {}


def _identity(article: Article | None, reference_id: uuid.UUID | None) -> tuple[Any, Any, Any]:
    if article is None:
        return None, None, None
    reference = next((r for r in article.live_references if r.id == reference_id), None)
    return article.noc, reference.pn if reference else None, reference.ncage if reference else None


def tree_order(rows: list[PhysicalPosition]) -> list[PhysicalPosition]:
    return sorted(rows, key=lambda r: (r.sns, r.co, r.al, r.cs_sns or "", r.cs_co or "", r.cs_al or "", r.created_at, str(r.id)))


async def confunfis_rows(db: AsyncSession, material: Material, rows: list[PhysicalPosition]) -> list[list[Any]]:
    articles = await _articles(db, {r.article_id for r in rows})
    out = []
    for r in tree_order(rows):
        noc, pn, ncage = _identity(articles.get(r.article_id) if r.article_id else None, r.article_reference_id)
        root = (r.sns, r.co, r.al) == ROOT
        cs = (None, None, None) if root and (r.cs_sns, r.cs_co, r.cs_al) in ((None, None, None), ROOT) else (r.cs_sns, r.cs_co, r.cs_al)
        out.append([*_cuf_columns(material), r.sns, r.co, r.al, _plain(r.qty), noc, pn, ncage, r.article_name, r.function_text, r.ct_sigle, *cs])
    return out


async def product_rows(db: AsyncSession, material: Material) -> list[list[Any]]:
    cuf_identity = [material.noc, material.part_number, material.ncage]
    return [
        [*cuf_identity, p.designation, p.pol_code, p.nae, p.noc, p.supply_unit, _plain(p.quantity) if p.quantity is not None else "N/A", p.unit]
        for p in await extras.live_products(db, material.id)
    ]


async def part_rows(db: AsyncSession, rows: list[PhysicalPosition]) -> list[list[Any]]:
    parents = {r.article_id for r in rows if r.article_id}
    parts = [p for p in await extras.live_parts(db) if p.parent_article_id in parents]
    articles = await _articles(db, parents | {p.part_article_id for p in parts})
    out = []
    for p in sorted(parts, key=lambda p: (articles[p.parent_article_id].noc or "", articles[p.parent_article_id].nombre, p.cop, p.alp, str(p.id))):
        parent = articles[p.parent_article_id]
        principal = parent.principal_reference
        part = articles.get(p.part_article_id) if p.part_article_id else None
        out.append([
            parent.noc, principal.pn if principal else None, principal.ncage if principal else None, p.cop, p.alp,
            *_identity(part, p.article_reference_id), _plain(p.quantity),
        ])
    return out


def _position(r: PhysicalPosition) -> list[Any]:
    return [r.sns, r.co, r.al, " ".join(x for x in (r.cs_sns, r.cs_co, r.cs_al) if x) or None]


async def extra_rows(db: AsyncSession, material: Material, rows: list[PhysicalPosition]) -> list[list[Any]]:
    by_id = {r.id: r for r in rows}
    return [
        [*_position(by_id[e.position_id]), e.sns, e.criterion, e.comment]
        for e in sorted(await extras.live_extras(db, material.id), key=lambda e: (by_id[e.position_id].sns, by_id[e.position_id].co, e.sns) if e.position_id in by_id else ("", "", e.sns))
        if e.position_id in by_id
    ]


async def incompatibility_rows(db: AsyncSession, material: Material, rows: list[PhysicalPosition]) -> list[list[Any]]:
    by_id = {r.id: r for r in rows}
    return [
        [*_position(by_id[i.row_a_id]), i.kind, *_position(by_id[i.row_b_id]), i.reason]
        for i in await extras.live_incompatibilities(db, material.id)
        if i.row_a_id in by_id and i.row_b_id in by_id
    ]


async def _help_sheets(db: AsyncSession, book, material: Material) -> list[str]:
    """SNS PERMITIDOS and TABLAS; returns the SNS codes, in order."""
    config = await cuf.normalized_config(db, material)
    positions = (
        await db.execute(select(SnsPosition).where(SnsPosition.version_id == material.catalog_version_id, SnsPosition.sns.in_(list(config))).order_by(SnsPosition.sns))
    ).scalars().all() if config else []
    ws = book.create_sheet(SNS_SHEET)
    for i, (header, width) in enumerate((("SNS", 10), ("NIVEL", 14), ("NOMBRE", 40), ("DESCRIPCIÓN", 80)), start=1):
        c = ws.cell(row=1, column=i, value=header)
        c.font, c.fill = _FONT, _FILL
        ws.column_dimensions[get_column_letter(i)].width = width
    for r, p in enumerate(positions, start=2):
        _cell(ws, r, 1, p.sns, True)
        _cell(ws, r, 2, p.level, False)
        _cell(ws, r, 3, p.name, False)
        _cell(ws, r, 4, p.description or "", False)
    ws.freeze_panes = "A2"
    tables = book.create_sheet(TABLES_SHEET)
    for t, code in enumerate(HELP_TABLES):
        col = t * 3 + 1
        values = (
            await db.execute(select(ReferenceValue.code, ReferenceValue.description).where(ReferenceValue.table_code == code, ReferenceValue.is_active).order_by(ReferenceValue.sort_order, ReferenceValue.code))
        ).all()
        for i, header in enumerate((code, "DESCRIPCIÓN")):
            c = tables.cell(row=1, column=col + i, value=header)
            c.font, c.fill = _FONT, _FILL
        tables.column_dimensions[get_column_letter(col)].width = 12
        tables.column_dimensions[get_column_letter(col + 1)].width = 36
        for r, (value, description) in enumerate(values, start=2):
            _cell(tables, r, col, value, True)
            _cell(tables, r, col + 1, description, False)
    return [p.sns for p in positions]


def _list(ws, column: int, source: str, rows: int) -> None:
    letter = get_column_letter(column)
    validation = DataValidation(type="list", formula1=source, allow_blank=True, showErrorMessage=False)
    validation.add(f"{letter}3:{letter}{rows + 2}")
    ws.add_data_validation(validation)


def _table_range(code: str, count: int) -> str:
    col = get_column_letter(HELP_TABLES.index(code) * 3 + 1)
    return f"'{TABLES_SHEET}'!${col}$2:${col}${max(count, 1) + 1}"


async def anexo_rows(db: AsyncSession, material: Material, rows: list[PhysicalPosition]) -> dict[str, list[list[Any]]]:
    """The Anexo XI's sheets as rows of cells (E17: what a baseline keeps to deliver)."""
    return {
        "CON_FUN_FIS": await confunfis_rows(db, material, rows),
        "TABLA PRODUCTOS FUNCIONALES": await product_rows(db, material),
        "TABLA DE PARTES": await part_rows(db, rows),
    }


def render_book(sheets: dict[str, list[list[Any]]], status_lines: list[tuple[str, str]] | None = None) -> bytes:
    """An Anexo XI from rows already made (E17: a baseline's snapshot), with an ESTADO DE VALIDACIÓN sheet if given."""
    book = openpyxl.Workbook()
    book.remove(book.active)
    specs = {spec.name: spec for spec in SHEETS}
    for name, values in sheets.items():
        _sheet(book, specs[name], values)
    if status_lines:
        validation_report.status_sheet(book, status_lines)
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()


async def build_book(db: AsyncSession, material: Material, kind: str, status: bool = True) -> bytes:
    """`status`: a working export starts with ESTADO DE VALIDACIÓN (E16); the delivery and the empty template do not."""
    book = openpyxl.Workbook()
    book.remove(book.active)
    rows = await confunfis.live_rows(db, material.id)
    specs = {spec.name: spec for spec in SHEETS}
    if kind == PLANTILLA:
        root = next((r for r in rows if (r.sns, r.co, r.al) == ROOT), None)
        base = [*_cuf_columns(material), *ROOT, 1, material.noc, material.part_number, material.ncage, material.name, root.function_text if root else None, None, None, None, None]
        fun = _sheet(book, specs["CON_FUN_FIS"], [base])
        products = _sheet(book, specs["TABLA PRODUCTOS FUNCIONALES"], [])
        _sheet(book, specs["TABLA DE PARTES"], [])
        sns = await _help_sheets(db, book, material)
        sizes = {code: len((await db.execute(select(ReferenceValue.id).where(ReferenceValue.table_code == code, ReferenceValue.is_active))).all()) for code in HELP_TABLES}
        limits = (await get_parameter(db, "confunfis"))["template"]
        n = limits["list_rows"]
        _list(fun, 14, '"S,N"', n)
        if 0 < len(sns) <= limits["max_sns_list"]:
            _list(fun, 5, f"'{SNS_SHEET}'!$A$2:$A${len(sns) + 1}", n)
        _list(products, 6, _table_range("NAE", sizes["NAE"]), n)
        _list(products, 8, _table_range("D155", sizes["D155"]), n)
        _list(products, 10, _table_range(extras.UNIT_TABLE, sizes[extras.UNIT_TABLE]), n)
    else:
        for name, values in (await anexo_rows(db, material, rows)).items():
            _sheet(book, specs[name], values)
        if kind == AAL:
            _sheet(book, specs[EXTRA_SHEET], await extra_rows(db, material, rows))
            _sheet(book, specs[INCOMPATIBILITY_SHEET], await incompatibility_rows(db, material, rows))
    if status and kind != PLANTILLA:
        validation_report.status_sheet(book, [(material.name, await validation_report.status_of(db, material))])
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()
