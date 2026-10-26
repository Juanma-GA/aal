"""The article's columns follow article_field_definition (E12): one per
field of the Fichero Carga but the life control pair, with the type of its
definition and, since E13, no length -- the definition's length and
decimals are the validation's, and the admin corrects them without code.
And "dónde se usa" is a registry E13/E14/E17 extend."""

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
        if prisma == "cdART":
            # The NOC's length is its format (13), checked in the database.
            assert isinstance(column.type, String) and column.type.length == f["length"] == 13
        elif f["data_type"] == "Numérico":
            assert isinstance(column.type, Numeric) and column.type.precision is None, prisma
        else:
            assert isinstance(column.type, String) and column.type.length is None, prisma


def test_numeric_lengths_follow_the_guide():
    """E13: digits without the comma (the guide's "tamaño" counts it):
    vaUsoArt 5,2 (it was 2,2: at most 0,99 €/h), caVoluArt 8; peso, largo,
    ancho and alto 7,2 = the guide's 8."""
    fields = {f["prisma_code"]: f for f in read_seed().fields}
    assert {p: (fields[p]["length"], fields[p]["decimals"]) for p in ("vaUsoArt", "caVoluArt", "caPesoArt", "caLargoArt", "imEstdArt")} == {
        "vaUsoArt": (5, 2), "caVoluArt": (8, None), "caPesoArt": (7, 2), "caLargoArt": (7, 2), "imEstdArt": (9, 2),
    }


def test_where_used_is_a_registry():
    """E12 has one provider (the article is a material's CUF); E13 adds the
    CONFUNFIS positions, E14 the parts and functional products, E17 the
    baseline warning: each registers its own, the endpoint stays."""
    assert [name for name, _fn in articles.USAGE_PROVIDERS] == ["cuf"]

    @articles.register_usage("prueba")
    async def provider(db, article, user):
        return [{"kind": "prueba"}]

    try:
        assert [name for name, _fn in articles.USAGE_PROVIDERS] == ["cuf", "prueba"]
    finally:
        articles.USAGE_PROVIDERS.pop()
