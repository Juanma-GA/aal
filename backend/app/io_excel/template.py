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

    def __post_init__(self) -> None:
        if self.header_rows not in (1, 2):
            raise ValueError("a template has one or two header rows")
        fields = [c.field for c in self.columns]
        if len(set(fields)) != len(fields):
            raise ValueError("duplicate field in a template")
        if not any(c.key for c in self.columns):
            raise ValueError("a template needs a key column")
        for c in self.columns:
            if len(c.headers) != self.header_rows:
                raise ValueError(f"column {c.field}: {self.header_rows} headers expected")
            if (c.zero_pad or c.choices) and c.type != ColumnType.TEXT:
                raise ValueError(f"column {c.field}: zero_pad and choices are for text columns")

    @property
    def first_data_row(self) -> int:
        return self.header_rows + 1

    @property
    def key_columns(self) -> tuple[Column, ...]:
        return tuple(c for c in self.columns if c.key)
