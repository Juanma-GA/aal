"""The module catalog seed (E02): the real file passes every check, and
each check catches what it is for."""

from dataclasses import replace

import pytest

from app.services.module_catalog import REQUIRED_RF, check_seed, find_cycle, read_seed


@pytest.fixture(scope="module")
def seed():
    return read_seed()


def test_the_real_seed_passes(seed):
    assert check_seed(seed) == []
    assert len(seed.groups) == 9
    assert len(seed.modules) == 45
    covered = {rf for m in seed.modules for rf, _ in m.requirements}
    assert covered >= set(REQUIRED_RF)


def test_states_of_the_seed(seed):
    states = {m.code: (m.status, m.route) for m in seed.modules}
    assert states["panel"] == ("disponible", "/materiales/:materialId")
    assert states["materiales"] == ("disponible", "/materiales/:materialId/ficha")
    # E10: common to every material, outside /materiales/:materialId.
    assert states["catalogo-normalizado"] == ("disponible", "/configuracion-funcional")
    # E12: the article master is global too.
    assert states["articulos"] == ("disponible", "/articulos")
    # E13: the CONFUNFIS of each material.
    assert states["confunfis"] == ("disponible", "/materiales/:materialId/confunfis")
    on = ("panel", "materiales", "catalogo-normalizado", "articulos", "confunfis")
    assert {s for code, (s, _) in states.items() if code not in on} == {"planificado"}


def _with(seed, code, **changes):
    return replace(seed, modules=[replace(m, **changes) if m.code == code else m for m in seed.modules])


def test_duplicate_code(seed):
    bad = replace(seed, modules=seed.modules + [seed.modules[0]])
    assert any("duplicate module panel" in p for p in check_seed(bad))


def test_unknown_group(seed):
    assert any("unknown group nada" in p for p in check_seed(_with(seed, "fta", group_code="nada")))


def test_unknown_dependency(seed):
    assert any("unknown dependency fantasma" in p for p in check_seed(_with(seed, "fta", dependencies=["fantasma"])))


def test_cycle(seed):
    # amfec -> candidatos -> ... ; make candidatos depend on fta (fta -> amfec -> candidatos).
    bad = _with(seed, "candidatos", dependencies=["fta"])
    problems = check_seed(bad)
    assert any(p.startswith("dependency cycle") for p in problems), problems


def test_find_cycle_on_its_own():
    assert find_cycle({"a": ["b"], "b": ["c"], "c": ["a"]}) == ["a", "b", "c", "a"]
    assert find_cycle({"a": ["b"], "b": [], "c": ["a"]}) is None


def test_uncovered_requirement(seed):
    bad = _with(seed, "teamcenter", requirements=[])
    assert "RF-32 is in no module" in check_seed(bad)


def test_states_and_routes(seed):
    assert any("unknown state" in p for p in check_seed(_with(seed, "fta", status="hecho")))
    assert any("without a route" in p for p in check_seed(_with(seed, "fta", status="disponible")))
    assert any("a route but not disponible" in p for p in check_seed(_with(seed, "fta", route="/x")))
    assert any("app path" in p for p in check_seed(_with(seed, "fta", status="disponible", route="https://x.es")))
