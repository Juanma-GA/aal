"""Sanitized errors: the client gets a stable code and a reference, the
technical detail goes to the server log under that same reference.

An error no route turned into an HTTPException is answered by
SanitizedErrorMiddleware with

    {"detail": {"code": "internal_error", "ref": "1a2b3c4d"}}          500

or, when the cause is the database,

    {"detail": {"code": "database_unavailable", "ref": ...}}           503
    {"detail": {"code": "database_not_migrated", "ref": ...}}          503

The exception's text, its class and the database's own message never reach
the response; `logger.exception` records them, with the traceback and the
request, under "ref=<ref>" -- the reference the frontend shows so the log
line can be found. The frontend translates the code into a sentence
(src/services/apiErrors.ts).
"""

import logging
import secrets
import socket

from sqlalchemy.exc import DBAPIError, InterfaceError, OperationalError, ProgrammingError
from starlette.responses import JSONResponse

logger = logging.getLogger("app.errors")


def new_error_ref() -> str:
    """A short reference shown to the user and written in the log line."""
    return secrets.token_hex(4)


def error_detail(code: str, ref: str | None = None, **params: object) -> dict:
    """The `detail` of a sanitized error: a code the frontend translates,
    the reference when there is a log line to find, and plain parameters."""
    detail: dict = {"code": code, **params}
    if ref:
        detail["ref"] = ref
    return detail


def is_missing_table(exc: BaseException) -> bool:
    """A table the migrations create is not there (database behind the code)."""
    orig = getattr(exc, "orig", None)
    text = f"{type(orig).__name__ if orig is not None else ''} {orig if orig is not None else exc}"
    return isinstance(exc, ProgrammingError) and ("UndefinedTable" in text or ("relation" in text and "does not exist" in text))


def is_database_unavailable(exc: BaseException) -> bool:
    """The database server cannot be reached or dropped the connection.

    asyncpg raises a ConnectionError (refused, reset) or a DNS failure
    (socket.gaierror) when the server is not there and a timeout when it
    does not answer -- not any OSError: a file error is not the database;
    SQLAlchemy wraps a lost connection in OperationalError/InterfaceError
    or flags it with connection_invalidated.
    """
    if isinstance(exc, (ConnectionError, socket.gaierror, TimeoutError)):
        return True
    if isinstance(exc, (OperationalError, InterfaceError)):
        return True
    if isinstance(exc, DBAPIError) and exc.connection_invalidated:
        return True
    try:
        import asyncpg  # noqa: PLC0415 -- only to recognise its connection errors
    except ImportError:  # pragma: no cover -- asyncpg is a hard dependency
        return False
    return isinstance(exc, (asyncpg.PostgresConnectionError, asyncpg.CannotConnectNowError, asyncpg.InterfaceError))


def unexpected_error_response(exc: BaseException, method: str, path: str) -> JSONResponse:
    """Logs the exception under a new reference and answers with its code."""
    ref = new_error_ref()
    if is_missing_table(exc):
        logger.exception(
            "ref=%s %s %s failed: a table is missing -- the migrations have not been applied (alembic upgrade head)",
            ref,
            method,
            path,
            extra={"ref": ref},
        )
        return JSONResponse(status_code=503, content={"detail": error_detail("database_not_migrated", ref)})
    if is_database_unavailable(exc):
        logger.exception("ref=%s %s %s failed: the database is not reachable", ref, method, path, extra={"ref": ref})
        return JSONResponse(status_code=503, content={"detail": error_detail("database_unavailable", ref)})
    logger.exception("ref=%s %s %s failed with an unexpected error", ref, method, path, extra={"ref": ref})
    return JSONResponse(status_code=500, content={"detail": error_detail("internal_error", ref)})


class SanitizedErrorMiddleware:
    """Pure ASGI middleware: catches an exception that escaped every route
    and handler before the response started, and answers it sanitized. Once
    a response has started nothing else can be sent: the exception is
    logged and re-raised."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False

        async def send_wrapper(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as exc:  # noqa: BLE001 -- answered sanitized, logged in full
            if started:
                logger.exception("%s %s failed after its response had started", scope.get("method"), scope.get("path"))
                raise
            response = unexpected_error_response(exc, scope.get("method", ""), scope.get("path", ""))
            await response(scope, receive, send)


async def validation_error_handler(_request, exc) -> JSONResponse:
    """A request that does not pass its schema: 422 with the fields and the
    kind of problem, never the values sent (a password must not come back
    or reach a log)."""
    fields = [
        {"field": ".".join(str(part) for part in err.get("loc", ())[1:]) or None, "type": err.get("type")}
        for err in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": error_detail("validation_error", fields=fields)})
