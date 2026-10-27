"""The time zone the backend's documents write their dates in (E16: the
validation report, the ESTADO DE VALIDACIÓN sheet): settings.timezone, an
IANA name, resolved on first use -- never on import -- and checked at
startup (app/main.py), so a missing zone stops the app with a clear message
instead of a 500 halfway through an export (HR7).

Windows has no zone database of its own: `zoneinfo` then reads the `tzdata`
package (in the lockfiles).
"""

from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.config import get_settings


@lru_cache(maxsize=1)
def zone() -> ZoneInfo:
    name = get_settings().timezone
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise RuntimeError(
            f"No se encuentra la zona horaria «{name}» (TIMEZONE): ni el sistema ni el paquete tzdata la tienen. "
            "En Windows, instala las dependencias del lockfile (npm run update) o corrige TIMEZONE."
        ) from exc


def check() -> None:
    """At startup: the zone resolves."""
    zone()
