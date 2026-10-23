"""The demo data (E10, D14): demo/ holds the four invented files, and the
materials of scripts/seed_demo_materials.py are those of its LEEME, with
valid identifiers."""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend" / "scripts"))

from seed_demo_materials import DEMO_MATERIALS  # noqa: E402

from app.schemas.materials import NCAGE_PATTERN, NOC_PATTERN  # noqa: E402


def test_demo_folder_has_the_four_files():
    names = sorted(p.name for p in (ROOT / "demo").iterdir())
    assert names == ["CONFUNFIS_DEMO_TRAMONTANA.xlsx", "CONF_FUN_DEMO.xlsx", "FICHERO_CARGA_DEMO.xlsx", "LEEME_DATOS_DEMO.md"]


def test_the_demo_materials_are_the_leemes_and_valid():
    leeme = (ROOT / "demo" / "LEEME_DATOS_DEMO.md").read_text(encoding="utf-8")
    assert len(DEMO_MATERIALS) == 5
    for name, noc, part_number, ncage, _description in DEMO_MATERIALS:
        assert f"| {name} | {noc} | {part_number} | {ncage} |" in leeme
        assert re.fullmatch(NOC_PATTERN, noc) and noc[6] == "X" and re.fullmatch(NCAGE_PATTERN, ncage)
