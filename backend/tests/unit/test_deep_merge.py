"""deep_merge (HR10): nested keys survive, overrides win, inputs untouched."""
import copy

from app.core.merge import deep_merge


def test_nested_key_not_in_override_is_kept():
    base = {"ui": {"sidebar": {"collapsed": False, "width": 280}, "theme": "light"}}
    override = {"ui": {"sidebar": {"width": 320}}}
    assert deep_merge(base, override) == {"ui": {"sidebar": {"collapsed": False, "width": 320}, "theme": "light"}}


def test_a_shallow_merge_would_lose_the_nested_key():
    """The bug HR10 is about: {**base, **override} drops sidebar.collapsed."""
    base = {"ui": {"sidebar": {"collapsed": False, "width": 280}}}
    override = {"ui": {"sidebar": {"width": 320}}}
    assert "collapsed" not in {**base, **override}["ui"]["sidebar"]
    assert deep_merge(base, override)["ui"]["sidebar"]["collapsed"] is False


def test_new_keys_are_added_at_every_depth():
    assert deep_merge({"a": {"b": 1}}, {"a": {"c": 2}, "d": 3}) == {"a": {"b": 1, "c": 2}, "d": 3}


def test_lists_are_replaced_not_merged():
    assert deep_merge({"levels": [1, 2, 3]}, {"levels": [4]}) == {"levels": [4]}


def test_scalar_replaces_mapping_and_mapping_replaces_scalar():
    assert deep_merge({"a": {"b": 1}}, {"a": 5}) == {"a": 5}
    assert deep_merge({"a": 5}, {"a": {"b": 1}}) == {"a": {"b": 1}}


def test_none_in_override_is_a_value():
    assert deep_merge({"a": 1}, {"a": None}) == {"a": None}


def test_empty_override_returns_an_equal_copy():
    base = {"a": {"b": [1, 2]}}
    merged = deep_merge(base, {})
    assert merged == base
    assert merged is not base
    assert merged["a"] is not base["a"]


def test_inputs_are_not_modified_and_result_shares_nothing():
    base = {"a": {"b": [1, 2], "c": {"d": 1}}}
    override = {"a": {"c": {"e": [9]}}}
    base_before, override_before = copy.deepcopy(base), copy.deepcopy(override)
    merged = deep_merge(base, override)
    merged["a"]["b"].append(3)
    merged["a"]["c"]["e"].append(10)
    assert base == base_before
    assert override == override_before
