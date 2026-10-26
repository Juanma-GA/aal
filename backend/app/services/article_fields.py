"""The 30 fields of an article as article_field_definition (E03) declares
them, and the generic validation of a value against its definition: type,
length, decimals, S/N values (E12). No field has a rule of its own here
(HR8): everything comes from the definition, so a change in the seed
changes the validation.

A value that cannot be stored (a text too long, a number with too many
digits or decimals, a letter in a number, an S/N field with another value)
is refused (`FieldError`, HR6: never cut). A missing value or a code that
is not in its reference table is stored and reported by AR-001
(app/validacion/articulos.py).
"""

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.io_excel.cells import CellError, normalize
from app.io_excel.template import Column, ColumnType
from app.models import FIELD_COLUMNS, ArticleFieldDefinition
from app.models.article import LIFE_CODE_FIELD, LIFE_QUANTITY_FIELD

NUMERIC = "Numérico"


@dataclass(frozen=True)
class FieldDef:
    prisma: str
    name: str
    header: str
    importance: str
    guide_field: str
    data_type: str
    length: int | None
    decimals: int | None
    table: str | None
    allowed_values: tuple[str, ...] | None
    help: dict[str, Any] | None
    sort_order: int

    @property
    def numeric(self) -> bool:
        return self.data_type == NUMERIC

    @property
    def column(self) -> str | None:
        """Its column in `article` (None for the life control pair)."""
        return FIELD_COLUMNS.get(self.prisma)

    def as_column(self, *, field: str | None = None, headers: tuple[str, ...] | None = None, key: bool = False) -> Column:
        """The io_excel column that reads and checks a value of the field."""
        if self.numeric:
            return Column(
                field or self.prisma, headers or (self.header,), ColumnType.DECIMAL, max_length=self.length, decimals=self.decimals or 0, key=key
            )
        choices = tuple((v, v) for v in self.allowed_values) if self.allowed_values else ()
        # Codes (of a table or S/N) are read in upper case: "kg" is KG.
        return Column(
            field or self.prisma, headers or (self.header,), max_length=self.length, choices=choices,
            upper=bool(self.table) and not choices, key=key,
        )


class FieldError(ValueError):
    def __init__(self, prisma: str, code: str, params: dict[str, Any]):
        super().__init__(code)
        self.prisma, self.code, self.params = prisma, code, params


async def field_defs(db: AsyncSession) -> dict[str, FieldDef]:
    """PRISMA code -> definition, in the Fichero Carga's order."""
    rows = (await db.execute(select(ArticleFieldDefinition).order_by(ArticleFieldDefinition.sort_order))).scalars().all()
    return {
        r.prisma_code: FieldDef(
            prisma=r.prisma_code, name=r.name, header=r.header or r.name, importance=r.importance, guide_field=r.guide_field,
            data_type=r.data_type, length=r.length, decimals=r.decimals, table=r.reference_table_code,
            allowed_values=tuple(r.allowed_values) if r.allowed_values else None, help=r.help, sort_order=r.sort_order,
        )
        for r in rows
    }


def coerce(definition: FieldDef, raw: Any) -> Any:
    """The value to store (None for empty), or FieldError."""
    try:
        return normalize(definition.as_column(), raw).value
    except CellError as exc:
        raise FieldError(definition.prisma, exc.code, exc.params) from None


# The fields the article keeps in article_life_control, not in a column.
LIFE_FIELDS = (LIFE_CODE_FIELD, LIFE_QUANTITY_FIELD)
