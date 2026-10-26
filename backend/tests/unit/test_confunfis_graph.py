"""The CONFUNFIS graph (E13, NT §9.1.7-9.1.8) with the norm's examples:
totals through the CS chain, alternative CS counted once (the computer in
the 10U or 12U cabinet; the laser with 3 AL × 2 CS = 1), the same NOC in two
huecos (the switch), orphans and cycles."""

from decimal import Decimal

from app.services.confunfis_graph import ROOT, Graph, Row

_n = 0


def row(sns, co="01", al="00", qty=1, cs=None):
    global _n
    _n += 1
    cs_sns, cs_co, cs_al = cs.split() if cs else (None, None, None)
    return Row(id=f"r{_n}", sns=sns, co=co, al=al, qty=Decimal(qty) if qty is not None else None, cs_sns=cs_sns, cs_co=cs_co, cs_al=cs_al)


def test_quantities_multiply_up_the_chain():
    rows = [row("000000"), row("A20000", cs="000000 01 00"), row("A21030", qty=6, cs="A20000 01 00"), row("A21031", qty=3, cs="A21030 01 00")]
    g = Graph(rows)
    assert g.total(("A21031", "01")) == 18 and g.total(("A21030", "01")) == 6
    assert g.chains(("A21031", "01")) == [[(Decimal(3), None), (Decimal(6), "A21030"), (Decimal(1), "A20000")]]
    assert [r.sns for r in g.children[("A20000", "01", "00")]] == ["A21030"]


def test_an_empty_cs_is_the_cuf_even_without_its_row():
    g = Graph([row("D12000", qty=2)])
    assert g.parent[next(iter(g.rows))] == ROOT and g.total(("D12000", "01")) == 2


def test_alternative_cs_count_once():
    """§9.1.8 case 2: the computer under the 10U or the 12U cabinet."""
    rows = [
        row("L48000", al="01"), row("L48000", al="02"),
        row("L41100", cs="L48000 01 01"), row("L41100", cs="L48000 01 02"),
        row("E19200", co="02", cs="L41100 01 00"),
    ]
    g = Graph(rows)
    assert g.total(("L41100", "01")) == 1 and g.total(("E19200", "02")) == 1
    assert all(g.is_cs_alternative(r) for r in rows[2:4]) and not g.is_cs_alternative(rows[4])
    assert all(g.is_alternative(r) for r in rows[:2])
    assert g.duplicates() == set()


def test_the_laser_3_al_by_2_cs_is_one():
    rows = [row("M10000", al="01"), row("M10000", al="02")] + [
        row("M11000", al=al, cs=f"M10000 01 {cs}") for al in ("01", "02", "03") for cs in ("01", "02")
    ]
    assert Graph(rows).total(("M11000", "01")) == 1


def test_the_switch_in_two_huecos():
    """§9.1.8 case 1: one NOC, two CO, each with its own CS: 1 + 1."""
    rows = [row("L46000"), row("L41100"), row("E19200", co="01", cs="L46000 01 00"), row("E19200", co="02", cs="L41100 01 00")]
    g = Graph(rows)
    assert (g.total(("E19200", "01")), g.total(("E19200", "02"))) == (1, 1)


def test_a_cs_in_two_different_huecos_adds_up():
    rows = [row("A10000", qty=2), row("B10000", qty=3), row("C10000", cs="A10000 01 00"), row("C10000", cs="B10000 01 00")]
    g = Graph(rows)
    assert g.total(("C10000", "01")) == 5 and len(g.chains(("C10000", "01"))) == 2


def test_orphans_and_duplicates():
    rows = [row("B31010", qty=4, cs="B300000000 01 00"), row("A24110", cs="A24000 01 00"), row("B32020", qty=4), row("B32020", qty=4)]
    g = Graph(rows)
    assert g.orphan == {rows[0].id: "malformed", rows[1].id: "not_found"}
    assert g.total(("B31010", "01")) is None and g.total(("B32020", "01")) == 4
    assert g.duplicates() == {rows[2].id, rows[3].id}


def test_cycles_are_found_and_have_no_total():
    rows = [row("X10000", cs="X20000 01 00"), row("X20000", cs="X10000 01 00"), row("X30000", cs="X10000 01 00"), row("Y10000", cs="Y10000 01 00")]
    g = Graph(rows)
    assert g.cycle_huecos == {("X10000", "01"), ("X20000", "01"), ("Y10000", "01")}
    assert all(g.total(h) is None for h in (("X10000", "01"), ("X30000", "01"), ("Y10000", "01")))
    assert g.in_cycle(rows[0]) and not g.in_cycle(rows[2])
