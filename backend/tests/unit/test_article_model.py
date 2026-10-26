"""The article's columns follow article_field_definition (E12): one per
field of the Fichero Carga but the life control pair, with the type, length
and decimals of its definition -- so the database stores exactly what the
validation accepts. And "dónde se usa" is a registry E13/E14/E17 extend."""

from sqlalchemy import Numeric, String

from app.models import FIELD_COLUMNS, Article
from app.services import articles
from app.services.article_fields import LIFE_FIELDS
from app.services.reference_seed import read_seed


def test_one_column_per_field_with_its_definition():
    fields = {f["prisma_code"]: f for f in read_seed().fields}
    assert set(FIELD_COLUMNS) | set(LIFE_FIELDS) == set(fields)
    columns = Article.__table__.columns
    for prisma, name in FIELD_COLUMNS.items():
        f, column = fields[prisma], columns[name]
        if f["data_type"] == "Numérico":
            assert isinstance(column.type, Numeric), prisma
            assert (column.type.precision, column.type.scale) == (f["length"], f["decimals"] or 0), prisma
        else:
            assert isinstance(column.type, String) and column.type.length == f["length"], prisma


def test_where_used_is_a_registry():
    """E12 has one provider (the article is a material's CUF); E13 adds the
    CONFUNFIS positions, E14 the parts and functional products, E17 the
    baseline warning: each registers its own, the endpoint stays."""
    assert [name for name, _fn in articles.USAGE_PROVIDERS] == ["cuf"]

    @articles.register_usage("prueba")
    async def provider(db, article):
        return [{"kind": "prueba"}]

    try:
        assert [name for name, _fn in articles.USAGE_PROVIDERS] == ["cuf", "prueba"]
    finally:
        articles.USAGE_PROVIDERS.pop()
