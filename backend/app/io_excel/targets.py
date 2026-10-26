"""What each consumer of the engine supplies (an import target), and the
registry app/services/import_jobs.py looks them up in by `kind` (the
import_job.template column).

A target module registers itself when imported (register(...)); the routes
module of each consumer imports it.

A target may also define `analyze(db, params, template, read) -> report`
when its records are not one row each (the CONF_FUN catalog groups rows by
SNS): its report has the same shape as analysis.analyze's ("columns",
"template_fields", "new", "modified", "unchanged", "errors", "warnings",
"counts", "pending"; "removed" optional), and the job uses it instead; and
`after_apply(db, job)`, run once the import is committed (the catalog
refreshes its tables' statistics; a reference table queues the
revalidation of the articles, E13).
"""

from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.io_excel.analysis import Stored
from app.io_excel.template import Template
from app.models import ImportJob, User


class ImportTarget(Protocol):
    kind: str

    def can_import(self, user: User, params: dict[str, Any]) -> bool:
        """Whether `user` may analyse and apply an import with `params`."""

    async def template(self, db: AsyncSession, params: dict[str, Any]) -> Template:
        """The template; HTTPException 404 when `params` name nothing."""

    async def stored(self, db: AsyncSession, params: dict[str, Any], template: Template) -> dict[tuple[Any, ...], Stored]:
        """The stored records, by key."""

    async def apply(self, db: AsyncSession, job: ImportJob, template: Template, user: User, ip: str | None) -> None:
        """Write job.report["pending"] in `db` (no commit), with an audit row
        per record. HTTPException 409 import_stale when a record changed
        since the analysis."""


_REGISTRY: dict[str, ImportTarget] = {}


def register(target: ImportTarget) -> ImportTarget:
    _REGISTRY[target.kind] = target
    return target


def get_target(kind: str) -> ImportTarget:
    return _REGISTRY[kind]
