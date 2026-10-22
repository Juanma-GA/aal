"""The server log is one JSON object per line (app/core/logging.py)."""
import json
import logging

from app.core.logging import JsonFormatter


def _format(record: logging.LogRecord) -> dict:
    line = JsonFormatter().format(record)
    assert "\n" not in line
    return json.loads(line)


def test_a_record_is_one_json_line_with_its_extra_fields():
    record = logging.LogRecord("app.test", logging.WARNING, __file__, 1, "hola %s", ("ñandú",), None)
    record.ref = "1a2b3c4d"
    entry = _format(record)
    assert entry["level"] == "WARNING"
    assert entry["logger"] == "app.test"
    assert entry["message"] == "hola ñandú"
    assert entry["ref"] == "1a2b3c4d"
    assert entry["time"].endswith("+00:00")


def test_an_exception_keeps_its_type_and_traceback():
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        record = logging.LogRecord("app.test", logging.ERROR, __file__, 1, "failed", None, sys.exc_info())
    entry = _format(record)
    assert entry["exc_type"] == "ValueError"
    assert "Traceback" in entry["exc_info"] and "boom" in entry["exc_info"]
