"""The pure pieces of E14: the cycles (of breakdowns, of "requiere") and
the symmetry of "excluye"."""

import uuid

from app.models import Incompatibility
from app.services.confunfis_extras import _cycles, same_incompatibility


def test_cycles():
    assert _cycles({"a": {"b"}, "b": {"c"}}) == set()
    assert _cycles({"a": {"b"}, "b": {"a"}, "c": {"a"}}) == {"a", "b"}
    assert _cycles({"a": {"a"}}) == {"a"}
    assert _cycles({"a": {"b"}, "b": {"c"}, "c": {"a"}, "d": {"c"}}) == {"a", "b", "c"}


def test_excluye_is_symmetric_and_requiere_directed():
    a, b = uuid.uuid4(), uuid.uuid4()
    excluye = Incompatibility(row_a_id=a, row_b_id=b, kind="excluye")
    requiere = Incompatibility(row_a_id=a, row_b_id=b, kind="requiere")
    assert same_incompatibility(excluye, b, a, "excluye") and same_incompatibility(excluye, a, b, "excluye")
    assert same_incompatibility(requiere, a, b, "requiere") and not same_incompatibility(requiere, b, a, "requiere")
    assert not same_incompatibility(excluye, a, b, "requiere")
