"""[stub] add_cache_ttl_to_tool_permissions

Revision ID: 007
Revises: 006
Create Date: squashed

No-op stub retained so Alembic can navigate from any old DB version
to the squashed baseline (013).  The real DDL lives in 001_baseline.py.
"""

from __future__ import annotations

revision: str = "007"
down_revision: str | None = "006"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
