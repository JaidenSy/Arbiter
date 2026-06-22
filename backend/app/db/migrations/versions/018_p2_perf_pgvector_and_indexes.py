"""P2 performance: pgvector semantic cache + composite indexes

Revision ID: 018
Revises: 017
Create Date: 2026-05-20
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "018"
down_revision: str | None = "017"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # ── Enable pgvector extension ─────────────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── Migrate input_embedding: JSONB → vector(384) ──────────────────────────
    # Existing embeddings are intentionally dropped: cache entries are ephemeral
    # and will be re-embedded on next cache write. The exact-hash path is unaffected.
    op.drop_column("cache_entries", "input_embedding")
    op.execute("ALTER TABLE cache_entries ADD COLUMN input_embedding vector(384)")

    # ── Composite indexes for high-frequency org-scoped queries ───────────────
    # PERF-02: audit/session queries filtered by org + time range
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_session_events_org_occurred "
        "ON session_events (org_id, occurred_at DESC)"
    )
    # Item-9: cache lookup + eviction queries filtered by org + tool
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_cache_entries_org_tool "
        "ON cache_entries (org_id, tool_name)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_cache_entries_org_tool")
    op.execute("DROP INDEX IF EXISTS ix_session_events_org_occurred")
    op.drop_column("cache_entries", "input_embedding")
    op.add_column("cache_entries", sa.Column("input_embedding", JSONB, nullable=True))
    # The vector extension is intentionally left installed on downgrade.
