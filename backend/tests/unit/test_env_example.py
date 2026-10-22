"""backend/.env.example lists exactly what backend/app/core/config.py reads.

A setting added to Settings without a line in .env.example (or a line left
behind after a setting is removed) fails here, so the example an operator
copies is never out of date. Each uncommented example value must also be
the setting's default: the file promises "a variable left out takes the
value shown here". A variable may be listed commented out ("# NAME=value")
when setting it by default would do harm (TEST_DATABASE_URL: never on a
server).
"""
import re
from pathlib import Path

from dotenv import dotenv_values

from app.core.config import Settings

EXAMPLE = Path(__file__).resolve().parents[2] / ".env.example"
LINE = re.compile(r"^(#\s)?([A-Z][A-Z0-9_]*)=", re.M)


def _example_names() -> dict[str, bool]:
    """name -> True if the line is active, False if commented out."""
    names: dict[str, bool] = {}
    for match in LINE.finditer(EXAMPLE.read_text(encoding="utf-8")):
        names[match.group(2)] = match.group(1) is None
    return names


def _setting_names() -> set[str]:
    return {name.upper() for name in Settings.model_fields}


def test_every_setting_is_in_the_example():
    missing = sorted(_setting_names() - set(_example_names()))
    assert not missing, f"config.py reads these but backend/.env.example does not list them: {missing}"


def test_the_example_lists_nothing_config_does_not_read():
    extra = sorted(set(_example_names()) - _setting_names())
    assert not extra, f"backend/.env.example lists variables config.py does not read: {extra}"


def test_example_values_are_the_defaults(monkeypatch):
    for name in _setting_names():
        monkeypatch.delenv(name, raising=False)
    defaults = Settings(_env_file=None).model_dump()
    from_example = Settings(_env_file=str(EXAMPLE)).model_dump()
    active = {name for name, on in _example_names().items() if on}
    values = dotenv_values(EXAMPLE)
    wrong = []
    for name in sorted(active):
        if values.get(name) in ("", None):
            assert defaults[name.lower()] in (None, ""), f"{name} is empty in the example but has a default"
            continue
        if from_example[name.lower()] != defaults[name.lower()]:
            wrong.append(f"{name}: example {from_example[name.lower()]!r}, default {defaults[name.lower()]!r}")
    assert not wrong, "backend/.env.example values that are not the defaults: " + "; ".join(wrong)
