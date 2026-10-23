"""One level of an SNS tree over a set of SNS of a version (a catalog
subcategory, E10, or a CUF's normalized configuration, E11): its roots (no
parent, or a parent outside the set) or the children of `parent`, with how
many children each has in the set. The set (a few thousand codes at most)
goes as a list, which the planner reads well even before the tables are
analysed."""

import uuid
from collections import Counter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SnsPosition


async def tree_level(db: AsyncSession, version_id: uuid.UUID, members: set[str], parent: str | None) -> list[tuple[SnsPosition, int]]:
    if not members:
        return []
    pairs = (
        await db.execute(select(SnsPosition.sns, SnsPosition.parent_sns).where(SnsPosition.version_id == version_id, SnsPosition.sns.in_(members)))
    ).all()
    if parent is None:
        wanted = {sns for sns, p in pairs if p is None or p not in members}
    else:
        wanted = {sns for sns, p in pairs if p == parent}
    children = Counter(p for _sns, p in pairs if p in wanted)
    if not wanted:
        return []
    nodes = (
        await db.execute(select(SnsPosition).where(SnsPosition.version_id == version_id, SnsPosition.sns.in_(wanted)).order_by(SnsPosition.sns))
    ).scalars().all()
    return [(n, children.get(n.sns, 0)) for n in nodes]
