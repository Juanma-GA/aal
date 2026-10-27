"""The Spanish texts of the documents the backend writes (E16: the
validation report, the ESTADO DE VALIDACIÓN sheet), read from the
frontend's locale (settings.i18n_es_path): one source for the screen and
the documents. `text("validation.report.title")`, with i18next's
`{{name}}` placeholders filled from the keyword arguments.
"""

import json
import logging
import re
from functools import lru_cache
from typing import Any

from app.core.config import backend_path, get_settings

logger = logging.getLogger("app.texts")
_PLACEHOLDER = re.compile(r"\{\{\s*(\w+)\s*\}\}")


@lru_cache(maxsize=1)
def _locale() -> dict[str, Any]:
    path = backend_path(get_settings().i18n_es_path)
    if not path.is_file():
        # Never a 500 halfway through an export (HR7): the app does not start without it.
        raise RuntimeError(f"No está el fichero de textos {path} (I18N_ES_PATH): el backend lo lee para sus documentos.")
    return json.loads(path.read_text(encoding="utf-8"))


def check() -> None:
    """At startup (app/main.py): the texts are there and readable."""
    _locale()


def lookup(key: str) -> Any:
    node: Any = _locale()
    for part in key.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def text(key: str, **params: Any) -> str:
    """The text of `key`; a missing one is logged and shown as its key (never an empty cell, HR7)."""
    found = lookup(key)
    if not isinstance(found, str):
        logger.warning("missing text %s", key)
        return key
    return _PLACEHOLDER.sub(lambda m: str(params.get(m.group(1), "")), found)
