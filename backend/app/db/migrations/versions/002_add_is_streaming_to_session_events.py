"""Add is_streaming column to session_events

Revision ID: 002
Revises: 001
Create Date: 2026-04-07
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "session_events",
        sa.Column(
            "is_streaming",
            sa.Boolean(),
            nullable=True,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("session_events", "is_streaming")
