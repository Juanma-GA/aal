"""The PALI module catalog (E02): read, check and load the seed
(app/seeds/module_catalog_seed.yaml).

- `read_seed()` parses the YAML and `check_seed()` lists every problem:
  duplicate codes, unknown groups, unknown or cyclic dependencies, a client
  requirement RF-01..RF-41 no module covers, an unknown state, a
  "disponible" module without a route (or a route on another state).
- `load_catalog(conn)` writes it, idempotently, on a synchronous
  connection (the migration's own, or `AsyncConnection.run_sync`): groups
  and modules are added or their texts updated; the status and route of a
  module already in the database are never overwritten (an admin changes
  them). Each module's requirements are replaced by the seed's. A module
  that left the seed stays (reported, never deleted: HR9).
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import Connection, delete, insert, select, update

from app.models import MODULE_STATUSES, ModuleCatalog, ModuleGroup, ModuleRequirement

SEED_PATH = Path(__file__).resolve().parents[1] / "seeds" / "module_catalog_seed.yaml"
# The client's requirements (functional specification): RF-01..RF-41.
REQUIRED_RF = tuple(f"RF-{n:02d}" for n in range(1, 42))
_TEXT_FIELDS = ("group_code", "name", "sort_order", "phase", "encargo", "objective", "inputs", "outputs", "deliverable", "dependencies")


class SeedError(ValueError):
    """The seed does not pass its checks (`problems` lists them all)."""

    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


@dataclass(frozen=True)
class SeedModule:
    code: str
    group_code: str
    name: str
    sort_order: int
    phase: str
    status: str
    encargo: str | None
    objective: str
    inputs: list[str]
    outputs: list[str]
    deliverable: str | None
    dependencies: list[str]
    route: str | None
    requirements: list[tuple[str, str]] = field(default_factory=list)

    def texts(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in _TEXT_FIELDS}


@dataclass(frozen=True)
class Seed:
    groups: list[tuple[str, str, int]]
    modules: list[SeedModule]


def read_seed(path: Path = SEED_PATH) -> Seed:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    groups = [(g["codigo"], g["nombre"], int(g["orden"])) for g in data["grupos"]]
    modules = [
        SeedModule(
            code=m["codigo"],
            group_code=m["grupo"],
            name=m["nombre"],
            sort_order=int(m["orden"]),
            phase=str(m["fase"]),
            status=m["estado"],
            encargo=m.get("encargo"),
            objective=m.get("objetivo") or "",
            inputs=list(m.get("entradas") or []),
            outputs=list(m.get("salidas") or []),
            deliverable=m.get("entregable"),
            dependencies=list(m.get("depende_de") or []),
            route=m.get("ruta"),
            requirements=[(r["id"], r["texto"]) for r in m.get("requisitos") or []],
        )
        for m in data["modulos"]
    ]
    return Seed(groups=groups, modules=modules)


def find_cycle(edges: dict[str, Iterable[str]]) -> list[str] | None:
    """A dependency cycle as [a, b, ..., a], or None."""
    state: dict[str, int] = {}  # 1 visiting, 2 done
    stack: list[str] = []

    def visit(node: str) -> list[str] | None:
        state[node] = 1
        stack.append(node)
        for nxt in edges.get(node, ()):
            if state.get(nxt) == 1:
                return stack[stack.index(nxt) :] + [nxt]
            if state.get(nxt) is None and nxt in edges:
                found = visit(nxt)
                if found:
                    return found
        stack.pop()
        state[node] = 2
        return None

    for node in edges:
        if state.get(node) is None:
            found = visit(node)
            if found:
                return found
    return None


def check_route(route: str) -> str | None:
    """Why a route is not acceptable, or None. An app path, never a URL."""
    if not route.startswith("/") or route.startswith("//") or "://" in route or any(c.isspace() for c in route):
        return "a route is an app path starting with a single /"
    return None


def check_seed(seed: Seed) -> list[str]:
    problems: list[str] = []
    group_codes = [g[0] for g in seed.groups]
    for code in {c for c in group_codes if group_codes.count(c) > 1}:
        problems.append(f"duplicate group {code}")
    codes = [m.code for m in seed.modules]
    for code in sorted({c for c in codes if codes.count(c) > 1}):
        problems.append(f"duplicate module {code}")
    known = set(codes)
    for m in seed.modules:
        if m.group_code not in group_codes:
            problems.append(f"{m.code}: unknown group {m.group_code}")
        for dep in m.dependencies:
            if dep not in known:
                problems.append(f"{m.code}: unknown dependency {dep}")
        if m.code in m.dependencies:
            problems.append(f"{m.code}: depends on itself")
        if m.status not in MODULE_STATUSES:
            problems.append(f"{m.code}: unknown state {m.status}")
        if m.status == "disponible" and not m.route:
            problems.append(f"{m.code}: disponible without a route")
        if m.status != "disponible" and m.route:
            problems.append(f"{m.code}: a route but not disponible")
        if m.route and check_route(m.route):
            problems.append(f"{m.code}: {check_route(m.route)}")
    cycle = find_cycle({m.code: m.dependencies for m in seed.modules})
    if cycle:
        problems.append("dependency cycle " + " -> ".join(cycle))
    covered = {rf for m in seed.modules for rf, _ in m.requirements}
    for rf in REQUIRED_RF:
        if rf not in covered:
            problems.append(f"{rf} is in no module")
    return problems


@dataclass(frozen=True)
class LoadReport:
    groups_added: int
    modules_added: int
    modules_updated: int
    # Codes in the database that the seed no longer has (kept).
    modules_not_in_seed: list[str]


def load_catalog(conn: Connection, seed: Seed | None = None) -> LoadReport:
    seed = seed or read_seed()
    problems = check_seed(seed)
    if problems:
        raise SeedError(problems)

    existing_groups = {row[0] for row in conn.execute(select(ModuleGroup.code))}
    groups_added = 0
    for code, name, order in seed.groups:
        if code in existing_groups:
            conn.execute(update(ModuleGroup).where(ModuleGroup.code == code).values(name=name, sort_order=order))
        else:
            conn.execute(insert(ModuleGroup).values(code=code, name=name, sort_order=order))
            groups_added += 1

    stored = {row.code: row for row in conn.execute(select(ModuleCatalog))}
    added = updated = 0
    for m in seed.modules:
        texts = m.texts()
        row = stored.get(m.code)
        if row is None:
            conn.execute(insert(ModuleCatalog).values(code=m.code, status=m.status, route=m.route, version=1, **texts))
            added += 1
        elif any(getattr(row, name) != value for name, value in texts.items()):
            # Texts only: status and route stay as an admin left them.
            conn.execute(update(ModuleCatalog).where(ModuleCatalog.code == m.code).values(version=row.version + 1, **texts))
            updated += 1
        conn.execute(delete(ModuleRequirement).where(ModuleRequirement.module_code == m.code))
        for i, (rf, text) in enumerate(m.requirements, start=1):
            conn.execute(insert(ModuleRequirement).values(module_code=m.code, rf_id=rf, text=text, sort_order=i))
    in_seed = {m.code for m in seed.modules}
    return LoadReport(
        groups_added=groups_added,
        modules_added=added,
        modules_updated=updated,
        modules_not_in_seed=sorted(set(stored) - in_seed),
    )
