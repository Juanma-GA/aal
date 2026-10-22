"""From a cell to a value, and from a value to the file, the screen and
JSON. The normalization rules, all of them here (E03 §2.2):

- Excel's own escapes (_xHHHH_) are undone; spaces before and after a text
  are removed (inside it they stay); an empty or blank cell is no value.
- TEXT: a number is written as text without ".0" (2.0 -> "2"); with
  `zero_pad` it is a code of that width ("2" -> "02", reported as a
  warning). With `choices`, the code or the label (any case) give the code.
  True/False or a date in a text column is an error.
- INTEGER: an integer number or text of digits (with a sign); 2.0 is 2;
  2.5 is an error.
- DECIMAL: a number, or text with "." or "," as the decimal mark (never
  both: thousands separators are refused); more decimals than declared is
  an error, never rounded.
- YES_NO: "S" or "N" in any case, or Excel's TRUE/FALSE.
- DATE: a date cell, or AAAAMMDD as a number or text.
- A text longer than `max_length`, or a number with more digits, is an
  error of the row: nothing is ever cut (HR6).
"""

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from openpyxl.utils.escape import unescape

from app.io_excel.template import Column, ColumnType


class CellError(Exception):
    """A cell that cannot become a value: an error code and its params."""

    def __init__(self, code: str, **params: Any):
        super().__init__(code)
        self.code = code
        self.params = params


@dataclass(frozen=True)
class Normalized:
    value: Any
    # A warning code and its params, when the value was read with a rule
    # worth telling (a number read as a padded code).
    warning: tuple[str, dict[str, Any]] | None = None


_INTEGER_RE = re.compile(r"^[+-]?\d+$")
_DECIMAL_RE = re.compile(r"^[+-]?\d+(\.\d+)?$")
_DATE_RE = re.compile(r"^\d{8}$")


def _number_text(raw: int | float) -> str:
    if isinstance(raw, float) and raw.is_integer():
        return str(int(raw))
    return str(raw)


def _digits(value: int | Decimal) -> int:
    return len(str(abs(value)).replace(".", "").lstrip("0")) or 1


def _text(col: Column, raw: Any) -> Normalized:
    warning = None
    if isinstance(raw, bool) or isinstance(raw, (datetime, date)):
        raise CellError("not_text")
    if isinstance(raw, (int, float)):
        text = _number_text(raw)
        if col.zero_pad and text.isdigit() and len(text) < col.zero_pad:
            padded = text.zfill(col.zero_pad)
            warning = ("number_read_as_code", {"value": text, "code": padded})
            text = padded
    else:
        text = str(raw)
    if col.choices:
        for code, label in col.choices:
            if text.casefold() in (code.casefold(), label.casefold()):
                return Normalized(code)
        raise CellError("not_a_choice", allowed=", ".join(label for _code, label in col.choices))
    if col.max_length is not None and len(text) > col.max_length:
        raise CellError("too_long", length=len(text), max=col.max_length)
    return Normalized(text, warning)


def _integer(col: Column, raw: Any) -> Normalized:
    if isinstance(raw, bool):
        raise CellError("not_integer")
    if isinstance(raw, float) and raw.is_integer():
        raw = int(raw)
    if isinstance(raw, str) and _INTEGER_RE.match(raw):
        raw = int(raw)
    if not isinstance(raw, int):
        raise CellError("not_integer")
    if col.max_length is not None and _digits(raw) > col.max_length:
        raise CellError("too_many_digits", max=col.max_length)
    return Normalized(raw)


def _decimal(col: Column, raw: Any) -> Normalized:
    if isinstance(raw, bool):
        raise CellError("not_decimal")
    if isinstance(raw, (int, float)):
        text = repr(raw) if isinstance(raw, float) else str(raw)
    elif isinstance(raw, str):
        if "," in raw and "." in raw:
            raise CellError("not_decimal")
        text = raw.replace(",", ".")
        if not _DECIMAL_RE.match(text):
            raise CellError("not_decimal")
    else:
        raise CellError("not_decimal")
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise CellError("not_decimal") from None
    if not value.is_finite():
        raise CellError("not_decimal")
    exponent = value.normalize().as_tuple().exponent
    if isinstance(exponent, int) and -exponent > col.decimals:
        raise CellError("too_many_decimals", max=col.decimals)
    value = value.quantize(Decimal(1).scaleb(-col.decimals)) if col.decimals else value.to_integral_value()
    if col.max_length is not None and _digits(value) > col.max_length:
        raise CellError("too_many_digits", max=col.max_length)
    return Normalized(value)


def _yes_no(raw: Any) -> Normalized:
    if isinstance(raw, bool):
        return Normalized(raw)
    if isinstance(raw, str) and raw.upper() in ("S", "N"):
        return Normalized(raw.upper() == "S")
    raise CellError("not_yes_no")


def _date(raw: Any) -> Normalized:
    if isinstance(raw, datetime):
        return Normalized(raw.date())
    if isinstance(raw, date):
        return Normalized(raw)
    if isinstance(raw, float) and raw.is_integer():
        raw = int(raw)
    text = str(raw) if isinstance(raw, (int, str)) and not isinstance(raw, bool) else ""
    if _DATE_RE.match(text):
        try:
            return Normalized(date(int(text[:4]), int(text[4:6]), int(text[6:])))
        except ValueError:
            pass
    raise CellError("not_a_date")


def normalize(col: Column, raw: Any) -> Normalized:
    """The value of a cell for `col` (see the module docstring), or
    CellError."""
    if isinstance(raw, str):
        raw = unescape(raw).replace("\r\n", "\n").strip()
        if raw == "":
            raw = None
    if raw is None:
        if col.required:
            raise CellError("required")
        return Normalized(None)
    if col.type == ColumnType.TEXT:
        return _text(col, raw)
    if col.type == ColumnType.INTEGER:
        return _integer(col, raw)
    if col.type == ColumnType.DECIMAL:
        return _decimal(col, raw)
    if col.type == ColumnType.YES_NO:
        return _yes_no(raw)
    return _date(raw)


def display(col: Column, value: Any) -> str:
    """How a value is written in the file and shown in the report."""
    if value is None:
        return ""
    if col.type == ColumnType.YES_NO:
        return "S" if value else "N"
    if col.type == ColumnType.DATE:
        return value.strftime("%Y%m%d")
    if col.choices:
        return dict(col.choices).get(value, value)
    return str(value)


def to_json(col: Column, value: Any) -> Any:
    """A value as JSON (the report keeps what apply will write)."""
    if value is None or col.type in (ColumnType.TEXT, ColumnType.INTEGER, ColumnType.YES_NO):
        return value
    if col.type == ColumnType.DECIMAL:
        return str(value)
    return value.isoformat()


def from_json(col: Column, value: Any) -> Any:
    if value is None or col.type in (ColumnType.TEXT, ColumnType.INTEGER, ColumnType.YES_NO):
        return value
    if col.type == ColumnType.DECIMAL:
        return Decimal(value)
    return date.fromisoformat(value)
