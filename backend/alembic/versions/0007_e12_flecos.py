"""E12 flecos: a catalog version is deleted logically (deleted_at), and an
admin annuls a sent, accepted or rejected SNS request with a reason
(annulled_at, annulled_by, annul_reason; the request is also deleted_at,
so it leaves every list and export but stays in the audit).

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-26

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("catalog_version", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    # The active version is never a deleted one.
    op.create_check_constraint("ck_catalog_version_active_not_deleted", "catalog_version", "NOT (is_active AND deleted_at IS NOT NULL)")
    op.add_column("sns_request", sa.Column("annulled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "sns_request",
        sa.Column("annulled_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True),
    )
    op.add_column("sns_request", sa.Column("annul_reason", sa.Text(), nullable=True))
    op.create_check_constraint(
        "ck_sns_request_annulled", "sns_request", "(annulled_at IS NULL) = (annul_reason IS NULL) AND (annulled_at IS NULL OR deleted_at IS NOT NULL)"
    )


def downgrade() -> None:
    op.drop_constraint("ck_sns_request_annulled", "sns_request", type_="check")
    op.drop_column("sns_request", "annul_reason")
    op.drop_column("sns_request", "annulled_by")
    op.drop_column("sns_request", "annulled_at")
    op.drop_constraint("ck_catalog_version_active_not_deleted", "catalog_version", type_="check")
    op.drop_column("catalog_version", "deleted_at")
