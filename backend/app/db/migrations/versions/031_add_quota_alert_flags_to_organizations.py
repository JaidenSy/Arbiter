"""Add quota_alert_80_sent and quota_alert_100_sent to organizations

Revision ID: 031
Revises: 030
Create Date: 2026-06-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "031"
down_revision: str | None = "030"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column(
            "quota_alert_80_sent",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "organizations",
        sa.Column(
            "quota_alert_100_sent",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("organizations", "quota_alert_100_sent")
    op.drop_column("organizations", "quota_alert_80_sent")
