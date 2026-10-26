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
