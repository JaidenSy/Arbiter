"""ensure all tool_permissions columns exist

Revision ID: 015
Revises: 014
Create Date: 2026-05-19

Belt-and-suspenders migration. Due to the migration chain chaos (duplicate
006, idempotent 013 that some DBs skipped, 014 that may not have landed),
any of org_id / granted_by / granted_by_user_id could be absent.

Every ALTER is guarded by an inspect() check so this is always a no-op on
a DB that already has the columns.
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import inspect, text

revision: str = "015"
down_revision: str | None = "014"
branch_labels: str | None = None
depends_on: str | None = None


def _col_names() -> set[str]:
    return {c["name"] for c in inspect(op.get_bind()).get_columns("tool_permissions")}


def upgrade() -> None:
    cols = _col_names()

    if "org_id" not in cols:
        op.execute(text(
            "ALTER TABLE tool_permissions "
            "ADD COLUMN org_id UUID REFERENCES organizations(id) ON DELETE CASCADE"
        ))

    if "granted_by" not in cols:
        op.execute(text(
            "ALTER TABLE tool_permissions ADD COLUMN granted_by TEXT"
        ))

    if "granted_by_user_id" not in cols:
        op.execute(text(
            "ALTER TABLE tool_permissions "
            "ADD COLUMN granted_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL"
        ))


def downgrade() -> None:
    cols = _col_names()
    if "granted_by_user_id" in cols:
        op.drop_column("tool_permissions", "granted_by_user_id")
    if "granted_by" in cols:
        op.drop_column("tool_permissions", "granted_by")
    if "org_id" in cols:
        op.drop_column("tool_permissions", "org_id")
