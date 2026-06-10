"""Add multi-hop tracing columns to sessions.

Adds parent_session_id (self-referential FK) and trace_id (shared chain UUID)
to the sessions table. Existing sessions get trace_id = id (each is its own root).

Revision ID: 029
Revises: 028
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "029"
down_revision = "028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column(
            "parent_session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sessions.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "sessions",
        sa.Column(
            "trace_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )

    # Back-fill: existing sessions are roots — trace_id = id
    op.execute("UPDATE sessions SET trace_id = id WHERE trace_id IS NULL")

    # Now make trace_id non-nullable
    op.alter_column("sessions", "trace_id", nullable=False)

    op.create_index("ix_sessions_parent_session_id", "sessions", ["parent_session_id"])
    op.create_index("ix_sessions_trace_id", "sessions", ["trace_id"])
    op.create_index("ix_sessions_trace_id_org_id", "sessions", ["trace_id", "org_id"])


def downgrade() -> None:
    op.drop_index("ix_sessions_trace_id_org_id", table_name="sessions")
    op.drop_index("ix_sessions_trace_id", table_name="sessions")
    op.drop_index("ix_sessions_parent_session_id", table_name="sessions")
    op.drop_column("sessions", "trace_id")
    op.drop_column("sessions", "parent_session_id")
