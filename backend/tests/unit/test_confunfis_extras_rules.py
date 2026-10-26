"""The pure pieces of E14: the cycles (of breakdowns, of "requiere"), the
symmetry of "excluye" and a part's total."""

import uuid
from decimal import Decimal
from types import SimpleNamespace

from app.models import Incompatibility
from app.services.confunfis_extras import _cycles, on_cycle, part_totals, same_incompatibility
from app.services.confunfis_graph import Graph, Row


def test_cycles():
    def nodes(edges):
        return set(_cycles(edges))

    assert nodes({"a": {"b"}, "b": {"c"}}) == set()
    assert nodes({"a": {"b"}, "b": {"a"}, "c": {"a"}}) == {"a", "b"}
    assert nodes({"a": {"a"}}) == {"a"}
    assert nodes({"a": {"b"}, "b": {"c"}, "c": {"a"}, "d": {"c"}}) == {"a", "b", "c"}
    # Closed through a second path (the review of E14): a2 is on a -> a2 -> b -> a.
    assert nodes({"a": {"a2", "b"}, "b": {"a"}, "a2": {"b"}}) == {"a", "a2", "b"}


def test_an_edge_between_two_cycles_is_on_none():
    cyclic = _cycles({"a": {"b"}, "b": {"a", "c"}, "c": {"d"}, "d": {"c"}})
    assert on_cycle(cyclic, "a", "b") and on_cycle(cyclic, "c", "d")
    assert not on_cycle(cyclic, "b", "c")


def test_a_part_total_is_none_when_a_hueco_has_none():
    rows = [
        Row(id="1", sns="A10000", co="01", al="00", qty=Decimal(2)),
        Row(id="2", sns="A20000", co="01", al="00", qty=Decimal(1), cs_sns="ZZZZZZ", cs_co="01", cs_al="00"),  # an orphan
    ]
    parent = uuid.uuid4()
    positions = [SimpleNamespace(article_id=parent, sns=r.sns, co=r.co) for r in rows]
    part = SimpleNamespace(id="p", parent_article_id=parent, quantity=Decimal(3))
    assert part_totals(Graph(rows), positions, [part]) == {"p": None}
    assert part_totals(Graph(rows[:1]), positions[:1], [part]) == {"p": Decimal(6)}


def test_excluye_is_symmetric_and_requiere_directed():
    a, b = uuid.uuid4(), uuid.uuid4()
    excluye = Incompatibility(row_a_id=a, row_b_id=b, kind="excluye")
    requiere = Incompatibility(row_a_id=a, row_b_id=b, kind="requiere")
    assert same_incompatibility(excluye, b, a, "excluye") and same_incompatibility(excluye, a, b, "excluye")
    assert same_incompatibility(requiere, a, b, "requiere") and not same_incompatibility(requiere, b, a, "requiere")
    assert not same_incompatibility(excluye, a, b, "requiere")
