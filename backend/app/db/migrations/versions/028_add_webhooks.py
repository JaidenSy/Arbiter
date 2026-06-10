"""Add webhooks and webhook_delivery_logs tables (#184)

Revision ID: 028
Revises: 027
Create Date: 2026-06-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "028"
down_revision: str | None = "027"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "webhooks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("secret", sa.String(255), nullable=False, comment="HMAC-SHA256 signing key"),
        sa.Column(
            "events",
            JSONB,
            nullable=False,
            server_default="[]",
            comment="List of subscribed event types",
        ),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_webhooks_org_id", "webhooks", ["org_id"])

    op.create_table(
        "webhook_delivery_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "webhook_id",
            UUID(as_uuid=True),
            sa.ForeignKey("webhooks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("response_status", sa.Integer, nullable=True),
        sa.Column("response_body", sa.Text, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("attempt", sa.Integer, nullable=False, server_default="1"),
        sa.Column(
            "delivered_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_webhook_delivery_logs_webhook_id", "webhook_delivery_logs", ["webhook_id"])


def downgrade() -> None:
    op.drop_table("webhook_delivery_logs")
    op.drop_table("webhooks")
