"""add tasks table for Mission Control

Revision ID: 019
Revises: 018
Create Date: 2026-05-21
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import inspect, text

revision: str = "019"
down_revision: str | None = "018"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if "tasks" in inspect(bind).get_table_names():
        return

    op.execute(text("""
        CREATE TABLE tasks (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id              UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            title               VARCHAR(255) NOT NULL,
            description         TEXT,
            status              VARCHAR(20)  NOT NULL DEFAULT 'pending',
            priority            VARCHAR(20)  NOT NULL DEFAULT 'normal',
            claimed_by_agent_id UUID REFERENCES agents(id) ON DELETE SET NULL,
            output              TEXT,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            claimed_at          TIMESTAMPTZ,
            completed_at        TIMESTAMPTZ
        )
    """))
    # Single-column org_id index — matches the model's `index=True` on org_id.
    op.execute(text(
        "CREATE INDEX ix_tasks_org_id ON tasks (org_id)"
    ))
    # Composite index for efficient queue polling (pending tasks per org).
    op.execute(text(
        "CREATE INDEX ix_tasks_org_status ON tasks (org_id, status)"
    ))


def downgrade() -> None:
    op.execute(text("DROP TABLE IF EXISTS tasks"))
