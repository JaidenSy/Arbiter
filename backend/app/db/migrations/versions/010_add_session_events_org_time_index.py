"""[stub] add_session_events_org_time_index

Revision ID: 010
Revises: 009
Create Date: squashed

No-op stub retained so Alembic can navigate from any old DB version
to the squashed baseline (013).  The real DDL lives in 001_baseline.py.
"""

from __future__ import annotations

revision: str = "010"
down_revision: str | None = "009"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
