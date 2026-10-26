"""A template, declared once and used both ways (import and export).

    Template(
        code="reference_table",
        sheet="D112",
        columns=(
            Column("code", ("Código",), ColumnType.TEXT, max_length=30, required=True, key=True),
            Column("description", ("Descripción",), required=True),
        ),
    )

With two header rows, each column has two headers: a group and its own
title (Anexo XI), or a name and a code (the Fichero Carga's names and PRISMA
codes). Equal consecutive groups are one merged cell in the export, and an
empty header cell is accepted on import where the column's header equals
the previous column's (that merged cell).
"""

from dataclasses import dataclass
from enum import StrEnum


class ColumnType(StrEnum):
    TEXT = "text"
    INTEGER = "integer"
    # A decimal number with at most `decimals` decimals.
    DECIMAL = "decimal"
    # S/N in the file, True/False as a value.
    YES_NO = "yes_no"
    # AAAAMMDD in the file, a date as a value.
    DATE = "date"


@dataclass(frozen=True)
class Column:
    field: str
    headers: tuple[str, ...]
    type: ColumnType = ColumnType.TEXT
    # TEXT: characters. INTEGER and DECIMAL: digits (decimals included).
    max_length: int | None = None
    decimals: int = 0
    required: bool = False
    # The value must be an (active) code of this reference table.
    ref_table: str | None = None
    # Part of the key that matches a row with a stored record.
    key: bool = False
    # TEXT only: a number found in the cell is a code of this width, padded
    # with zeros ("2" -> "02").
    zero_pad: int | None = None
    # TEXT only: (stored code, label written in the file). The file shows
    # the label; the code or the label are both read back (any case).
    choices: tuple[tuple[str, str], ...] = ()
    # TEXT only: read in upper case ("a21031" -> "A21031").
    upper: bool = False
    # A column past the template's own, without a header: read when the
    # file has it (a text split by an unescaped quote in the source, CONF_FUN
    # CN-005), never written. Its header cell is accepted empty.
    extra: bool = False
    # Column width in the export (Excel character units).
    width: float | None = None

    @property
    def title(self) -> str:
        """The column's own header (the last row's)."""
        return self.headers[-1]


@dataclass(frozen=True)
class Template:
    code: str
    sheet: str
    columns: tuple[Column, ...]
    header_rows: int = 1
    # A key may repeat (a catalog where a code appears in several rows): the
    # consumer's own analysis groups the rows, the reader does not refuse
    # them as duplicates.
    unique_keys: bool = True
    # The header rows the reader checks (1-based); None: all of them. The
    # Fichero Carga is recognized by its PRISMA codes (row 2) only (E12).
    checked_header_rows: tuple[int, ...] | None = None
    # How the header looks in the export: "aal" (bold on a grey fill,
    # frozen), or "fichero_carga" (the official SIGLE template's: Calibri 8
    # bold, wrapped, the codes' row on a white fill, nothing frozen).
    header_look: str = "aal"

    def __post_init__(self) -> None:
        if self.header_rows not in (1, 2):
            raise ValueError("a template has one or two header rows")
        if self.header_look not in ("aal", "fichero_carga"):
            raise ValueError(f"unknown header look {self.header_look}")
        if self.checked_header_rows is not None and not set(self.checked_header_rows) <= set(range(1, self.header_rows + 1)):
            raise ValueError("checked_header_rows outside the header rows")
        fields = [c.field for c in self.columns]
        if len(set(fields)) != len(fields):
            raise ValueError("duplicate field in a template")
        if not any(c.key for c in self.columns):
            raise ValueError("a template needs a key column")
        for c in self.columns:
            if len(c.headers) != self.header_rows:
                raise ValueError(f"column {c.field}: {self.header_rows} headers expected")
            if (c.zero_pad or c.choices or c.upper) and c.type != ColumnType.TEXT:
                raise ValueError(f"column {c.field}: zero_pad, choices and upper are for text columns")
        extras = [i for i, c in enumerate(self.columns) if c.extra]
        if extras and extras != list(range(len(self.columns) - len(extras), len(self.columns))):
            raise ValueError("extra columns go last")

    @property
    def first_data_row(self) -> int:
        return self.header_rows + 1

    @property
    def written_columns(self) -> tuple[Column, ...]:
        """The columns of the export (all but the extra ones)."""
        return tuple(c for c in self.columns if not c.extra)

    @property
    def key_columns(self) -> tuple[Column, ...]:
        return tuple(c for c in self.columns if c.key)
