"""The sheet CON_FUN_FIS of the Anexo XI (NT 10/17) as an io_excel
template (E13): read here for scripts/seed_demo_confunfis.py, and the base
E15 extends into the full import (analyze -> apply, round trip, the other
sheets).

Two header rows: the blocks (DATOS DEL CUF, POSICIÓN FUNCIONAL, COMPONENTE
FÍSICO, CONJUNTO SUPERIOR; merged cells) and the columns -- only the second
row is checked. Every cell is read as text (CO and AL padded to two
digits, codes in upper case) but QTY, a number with decimals: a value the
NT forbids (1,5) is read, stored and observed, never refused here.
"""

from typing import Any

from app.io_excel.reader import Limits, ReadResult, read_rows
from app.io_excel.template import Column, ColumnType, Template

SHEET = "CON_FUN_FIS"

_CUF, _POS, _COMP, _CS = "DATOS DEL CUF", "POSICIÓN FUNCIONAL", "COMPONENTE FÍSICO", "CONJUNTO SUPERIOR"

TEMPLATE = Template(
    code="confunfis_sheet",
    sheet=SHEET,
    header_rows=2,
    checked_header_rows=(2,),
    unique_keys=False,
    columns=(
        Column("cuf_noc", (_CUF, "CUF"), upper=True, width=16),
        Column("cuf_name", (_CUF, "NOMBRE CUF"), width=28),
        Column("cuf_pn", (_CUF, "P/N CUF"), width=14),
        Column("cuf_ncage", (_CUF, "NCAGE CUF"), upper=True, width=10),
        Column("sns", (_POS, "SNS"), upper=True, key=True, width=9),
        Column("co", (_POS, "CO"), zero_pad=2, width=5),
        Column("al", (_POS, "AL"), zero_pad=2, width=5),
        Column("qty", (_POS, "QTY"), ColumnType.DECIMAL, decimals=6, width=6),
        Column("noc", (_COMP, "NOC"), upper=True, width=16),
        Column("pn", (_COMP, "P/N"), width=16),
        Column("ncage", (_COMP, "NCAGE"), upper=True, width=8),
        Column("article_name", (_COMP, "NOMBRE ARTÍCULO"), width=36),
        Column("function_text", (_COMP, "FUNCIÓN ARTÍCULO"), width=48),
        Column("ct_sigle", (_COMP, "CT SIGLE"), upper=True, width=8),
        Column("cs_sns", (_CS, "SNS CONJUNTO SUPERIOR"), upper=True, width=12),
        Column("cs_co", (_CS, "CO"), zero_pad=2, width=5),
        Column("cs_al", (_CS, "AL"), zero_pad=2, width=5),
    ),
)

# What save_row takes as the row and as the article's identity.
ROW_FIELDS = ("sns", "co", "al", "qty", "article_name", "function_text", "ct_sigle", "cs_sns", "cs_co", "cs_al")
IDENTITY_FIELDS = ("noc", "pn", "ncage")


def read_sheet(data: bytes, limits: Limits) -> ReadResult:
    return read_rows(TEMPLATE, data, limits)


def split(values: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """A row of the sheet as (row values, article identity)."""
    return {k: values.get(k) for k in ROW_FIELDS}, {k: values.get(k) for k in IDENTITY_FIELDS}


# ── the other sheets of the Anexo XI (E14) ───────────────────────────────

PRODUCTS_SHEET = "TABLA PRODUCTOS FUNCIONALES"
_PF = "PRODUCTOS FUNCIONALES"

PRODUCTS_TEMPLATE = Template(
    code="functional_products_sheet",
    sheet=PRODUCTS_SHEET,
    header_rows=2,
    checked_header_rows=(2,),
    unique_keys=False,
    columns=(
        Column("cuf_noc", ("CUF", "NOC"), upper=True, width=16),
        Column("cuf_pn", ("CUF", "P/N"), width=14),
        Column("cuf_ncage", ("CUF", "NCAGE"), upper=True, width=10),
        Column("designation", (_PF, "DESIGNACIÓN"), key=True, width=44),
        Column("pol_code", (_PF, "Nº de Código OTAN/Nacional"), upper=True, width=12),
        Column("nae", (_PF, "N/A/E"), upper=True, width=6),
        Column("noc", (_PF, "NOC"), upper=True, width=16),
        Column("supply_unit", (_PF, "UNIDAD DE SUMINISTRO"), upper=True, width=12),
        # Text: "N/A" is a product in bulk.
        Column("quantity", (_PF, "CANTIDAD"), width=9),
        Column("unit", (_PF, "UNIDAD DE MEDIDA"), upper=True, width=10),
    ),
)
PRODUCT_FIELDS = ("designation", "pol_code", "nae", "noc", "supply_unit", "quantity", "unit")

PARTS_SHEET = "TABLA DE PARTES"
_ART, _PARTS = "ARTÍCULO", "PARTES"

PARTS_TEMPLATE = Template(
    code="article_parts_sheet",
    sheet=PARTS_SHEET,
    header_rows=2,
    checked_header_rows=(2,),
    unique_keys=False,
    columns=(
        Column("parent_noc", (_ART, "NOC"), upper=True, key=True, width=16),
        Column("parent_pn", (_ART, "P/N"), width=14),
        Column("parent_ncage", (_ART, "NCAGE"), upper=True, width=10),
        Column("cop", (_ART, "COP"), zero_pad=2, width=5),
        Column("alp", (_ART, "ALP"), zero_pad=2, width=5),
        Column("noc", (_PARTS, "NOC"), upper=True, width=16),
        Column("pn", (_PARTS, "P/N"), width=16),
        Column("ncage", (_PARTS, "NCAGE"), upper=True, width=8),
        Column("quantity", (_PARTS, "CANTIDAD"), ColumnType.DECIMAL, decimals=6, width=9),
    ),
)


def read_products(data: bytes, limits: Limits) -> ReadResult:
    return read_rows(PRODUCTS_TEMPLATE, data, limits)


def read_parts(data: bytes, limits: Limits) -> ReadResult:
    return read_rows(PARTS_TEMPLATE, data, limits)


def split_part(values: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """A row of TABLA DE PARTES as (its parent's identity, the part's values, the part's identity)."""
    parent = {"noc": values.get("parent_noc"), "pn": values.get("parent_pn"), "ncage": values.get("parent_ncage")}
    return parent, {k: values.get(k) for k in ("cop", "alp", "quantity")}, {k: values.get(k) for k in IDENTITY_FIELDS}
