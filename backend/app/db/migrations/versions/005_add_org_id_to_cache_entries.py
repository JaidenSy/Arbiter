"""[stub] add_org_id_to_cache_entries

Revision ID: 005
Revises: 004
Create Date: squashed

No-op stub retained so Alembic can navigate from any old DB version
to the squashed baseline (013).  The real DDL lives in 001_baseline.py.
"""

from __future__ import annotations

revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
