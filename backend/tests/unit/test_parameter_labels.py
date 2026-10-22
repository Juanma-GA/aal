"""Every parameter (PARAMETER_DEFAULTS) has its group and label in the
Spanish locale, so Settings -> Parámetros never shows a raw key (HR21)."""

import json
from pathlib import Path

from app.services.parameters import PARAMETER_DEFAULTS

ES = Path(__file__).resolve().parents[3] / "src" / "i18n" / "locales" / "es.json"


def _leaves(value: dict, prefix: str = "") -> list[str]:
    out = []
    for key, v in value.items():
        out += _leaves(v, f"{prefix}{key}.") if isinstance(v, dict) else [f"{prefix}{key}"]
    return out


def test_every_parameter_has_a_spanish_label():
    texts = json.loads(ES.read_text(encoding="utf-8"))["settings"]["parameters"]
    missing = [key for key in PARAMETER_DEFAULTS if key not in texts["groups"]]
    missing += [path for value in PARAMETER_DEFAULTS.values() for path in _leaves(value) if path not in texts["labels"]]
    assert missing == [], f"src/i18n/locales/es.json settings.parameters lacks: {missing}"
