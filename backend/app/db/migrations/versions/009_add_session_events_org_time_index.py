"""add composite index on session_events(org_id, occurred_at)

Revision ID: 009
Revises: 008
Create Date: 2026-05-14
"""

from __future__ import annotations

from alembic import op

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_session_events_org_occurred",
        "session_events",
        ["org_id", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_session_events_org_occurred", table_name="session_events")
