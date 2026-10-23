"""Level and parent from the SNS code (NT §6, fig. 6-2) and the repair of a
split description (CN-005), E10."""

import pytest

from app.services.catalog import derived_level, derived_parent, pending_mark, repair_split


@pytest.mark.parametrize(
    "sns, level, parent",
    [
        ("000000", "SISTEMA", None),
        ("A20000", "SISTEMA", None),
        ("A21000", "SUBSISTEMA", "A20000"),
        ("A22100", "SUBSUBSISTEMA", "A22000"),
        ("A21030", "CONJUNTO", "A21000"),
        ("A21326", "SUBCONJUNTO", "A21320"),
        ("ZLC150", "CONJUNTO", "ZLC100"),
        ("L4121C", "SUBCONJUNTO", "L41210"),
        ("B34510", "CONJUNTO", "B34500"),
        ("ZDM100", "SUBSUBSISTEMA", "ZDM000"),
        ("AB0C00", "SUBSUBSISTEMA", "AB0000"),
    ],
)
def test_level_and_parent_from_the_code(sns, level, parent):
    assert (derived_level(sns), derived_parent(sns)) == (level, parent)


def test_a_split_description_is_joined_without_the_leftover_quotes():
    assert repair_split('"EQUIPOS DE RADIO DE COMBATE', ' INCLUIDAS ANTENAS Y CABLEADO DE RF"') == (
        "EQUIPOS DE RADIO DE COMBATE, INCLUIDAS ANTENAS Y CABLEADO DE RF",
        True,
    )
    assert repair_split("NORMAL", None) == ("NORMAL", False)
    assert repair_split(None, None) == ("", False)
    assert repair_split("", " SOLO LA SEGUNDA") == ("SOLO LA SEGUNDA", True)


@pytest.mark.parametrize("text, mark", [("PTE", "PTE"), (" pte ", "PTE"), ("TBD PENDIENTE", "TBD"), ("PTE DE REVISAR", None), ("", None)])
def test_pending_descriptions(text, mark):
    assert pending_mark(text) == mark
