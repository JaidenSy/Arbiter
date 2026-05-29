"""Add user_id FK to session_events table

Revision ID: 022
Revises: 021
Create Date: 2026-05-29
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "022"
down_revision: str | None = "021"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "session_events",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_session_events_user_id",
        "session_events",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_session_events_user_id", table_name="session_events")
    op.drop_column("session_events", "user_id")
