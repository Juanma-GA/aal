"""Edits cells of a workbook with openpyxl, for a browser check
(scripts/verify-reference-tables.mjs, E03): the file a person would have
changed in Excel.

    python scripts/verify_edit_xlsx.py IN.xlsx OUT.xlsx HOJA B2="Nuevo texto" ...
                                                              (from backend/)
"""

import sys

from _common import utf8_output

import openpyxl


def main() -> int:
    if len(sys.argv) < 5:
        print(__doc__, file=sys.stderr)
        return 1
    source, target, sheet, *changes = sys.argv[1:]
    workbook = openpyxl.load_workbook(source)
    for change in changes:
        cell, _, value = change.partition("=")
        workbook[sheet][cell] = value
        workbook[sheet][cell].data_type = "s"
    workbook.save(target)
    print(f"Editadas {len(changes)} celdas de {sheet}")
    return 0


if __name__ == "__main__":
    utf8_output()
    sys.exit(main())
