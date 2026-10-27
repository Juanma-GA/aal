"""The sheets of the CONFUNFIS book (E15): the three of the Anexo XI
(app/services/confunfis_sheet.py, read since E13/E14) and the two the
"Libro AAL" adds, in its own format:

- FUNCIONES ADICIONALES: FILA DE LA CONFUNFIS (SNS, CO, AL, CONJUNTO
  SUPERIOR as "SNS CO AL", empty for the CUF) and FUNCIÓN ADICIONAL (SNS
  ADICIONAL, CRITERIO -- a code of CRITERIO_MULTIFUNCION --, COMENTARIO).
- INCOMPATIBILIDADES: FILA A (the same four), TIPO (excluye / requiere),
  FILA B (the same four) and MOTIVO.

A row is named by its position and CS; when several rows share them (a
duplicate), the first one is meant.

`read_book` reads every sheet it knows, in any order: CON_FUN_FIS is the
only one required; the others may be missing; a sheet it does not know is
listed (the template's help sheets, the official book's auxiliary ones).
`SHEETS` says how each is written (app/services/anexo_xi_export.py).
"""

from dataclasses import dataclass

from app.core.texts import text
from app.io_excel.reader import Limits, ReadResult, read_rows, sheet_names
from app.io_excel.template import Column, ColumnType, Template
from app.services.confunfis_sheet import PARTS_TEMPLATE, PRODUCTS_TEMPLATE, TEMPLATE

EXTRA_SHEET, INCOMPATIBILITY_SHEET = "FUNCIONES ADICIONALES", "INCOMPATIBILIDADES"
_ROW, _EXTRA = "FILA DE LA CONFUNFIS", "FUNCIÓN ADICIONAL"


def _position(prefix: str, block: str) -> tuple[Column, ...]:
    return (
        Column(f"{prefix}sns", (block, "SNS"), upper=True, key=True, width=10),
        Column(f"{prefix}co", (block, "CO"), zero_pad=2, width=5),
        Column(f"{prefix}al", (block, "AL"), zero_pad=2, width=5),
        Column(f"{prefix}cs", (block, "CONJUNTO SUPERIOR"), upper=True, width=16),
    )


EXTRAS_TEMPLATE = Template(
    code="extra_functions_sheet", sheet=EXTRA_SHEET, header_rows=2, checked_header_rows=(2,), unique_keys=False,
    columns=(
        *_position("", _ROW),
        Column("sns_extra", (_EXTRA, "SNS ADICIONAL"), upper=True, width=12),
        Column("criterion", (_EXTRA, "CRITERIO"), width=20),
        Column("comment", (_EXTRA, "COMENTARIO"), width=48),
    ),
)

INCOMPATIBILITIES_TEMPLATE = Template(
    code="incompatibilities_sheet", sheet=INCOMPATIBILITY_SHEET, header_rows=2, checked_header_rows=(2,), unique_keys=False,
    columns=(
        *_position("a_", "FILA A"),
        Column("kind", ("TIPO", "TIPO"), width=10),
        *_position("b_", "FILA B"),
        Column("reason", ("MOTIVO", "MOTIVO"), width=48),
    ),
)

OFFICIAL = (TEMPLATE, PRODUCTS_TEMPLATE, PARTS_TEMPLATE)
OWN = (EXTRAS_TEMPLATE, INCOMPATIBILITIES_TEMPLATE)
# The headers written otherwise than they are checked: the official book's
# own spelling (row 2 is compared trimmed, so both read).
EXPORT_HEADERS = {(TEMPLATE.sheet, "cuf_pn"): " P/N CUF"}
# Written as numbers (the template reads them as text: "N/A" is a product in bulk).
NUMBER_FIELDS = {(PRODUCTS_TEMPLATE.sheet, "quantity")}


@dataclass(frozen=True)
class ExportColumn:
    field: str
    header: str
    width: float
    text: bool


@dataclass(frozen=True)
class SheetSpec:
    name: str
    template: Template
    # Row 1: (first, last column, 1-based, its block title), merged.
    blocks: tuple[tuple[int, int, str], ...]
    columns: tuple[ExportColumn, ...]


def _spec(template: Template) -> SheetSpec:
    blocks: list[tuple[int, int, str]] = []
    for i, col in enumerate(template.columns, start=1):
        if blocks and blocks[-1][2] == col.headers[0]:
            blocks[-1] = (blocks[-1][0], i, col.headers[0])
        else:
            blocks.append((i, i, col.headers[0]))
    columns = tuple(
        ExportColumn(
            c.field, EXPORT_HEADERS.get((template.sheet, c.field), c.title), c.width or 12,
            c.type == ColumnType.TEXT and (template.sheet, c.field) not in NUMBER_FIELDS,
        )
        for c in template.columns
    )
    return SheetSpec(template.sheet, template, tuple(blocks), columns)


SHEETS = tuple(_spec(t) for t in (*OFFICIAL, *OWN))
KNOWN = {t.sheet for t in (*OFFICIAL, *OWN)}


def read_book(template: Template, data: bytes, limits: Limits) -> ReadResult:
    """CON_FUN_FIS (`template`, required) and, in `.sheets`, every other
    sheet it knows that the file has; the rest in `.ignored_sheets`."""
    names = sheet_names(data)
    read = read_rows(template, data, limits)
    for other in (*OFFICIAL[1:], *OWN):
        if other.sheet in names:
            read.sheets[other.sheet] = read_rows(other, data, limits)
    # The ESTADO DE VALIDACIÓN sheet of a working export (E16) is ours too: not read, not reported.
    read.ignored_sheets = [n for n in names if n not in KNOWN and n != text("validation.status.sheet")]
    return read
