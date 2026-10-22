"""Generic Excel import/export engine (E03).

- template.py: the declarative template (sheet, one or two header rows,
  columns with their type, length, obligation, reference table, key).
- cells.py: how a cell read from the file becomes a value (the explicit
  normalization rules) and how a value is shown and stored in JSON.
- reader.py: the file's safety checks and the reading of its rows.
- writer.py: the exact export of a template.
- analysis.py: a read file against what is stored -> the report (new,
  modified field by field, unchanged, errors, warnings).
- targets.py: what each consumer supplies (its template, its stored
  records, how to apply); app/services/import_jobs.py runs the two phases.

The first consumer is the "Tabla de referencia" template
(app/services/reference_import.py); E10 (CONF_FUN), E12 (Fichero Carga) and
E15 (Anexo XI) add theirs.
"""
