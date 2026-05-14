"""add_org_id_to_agents_mcp_servers_vault_secrets

Revision ID: 003
Revises: 002
Create Date: 2026-05-13

Adds org_id FK to agents, mcp_servers, and vault_secrets — these tables
were created before multi-tenancy (orgs) existed and were never backfilled.

org_id is added as nullable so the migration runs cleanly on existing rows.
The ORM models enforce NOT NULL at insert time, so no new rows can lack it.

Also replaces the old name-scoped unique constraints with org-scoped ones:
  - mcp_servers: (name) → (org_id, name)
  - vault_secrets: (name, agent_id) → (org_id, name, agent_id)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # ── agents: add org_id ────────────────────────────────────────────────────
    op.add_column(
        "agents",
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_agents_org_id",
        "agents",
        "organizations",
        ["org_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # ── mcp_servers: add org_id, swap unique constraint ───────────────────────
    op.add_column(
        "mcp_servers",
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_mcp_servers_org_id",
        "mcp_servers",
        "organizations",
        ["org_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_constraint("mcp_servers_name_key", "mcp_servers", type_="unique")
    op.create_unique_constraint(
        "uq_mcp_server_name_per_org",
        "mcp_servers",
        ["org_id", "name"],
    )

    # ── vault_secrets: add org_id, swap unique constraint ─────────────────────
    op.add_column(
        "vault_secrets",
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_vault_secrets_org_id",
        "vault_secrets",
        "organizations",
        ["org_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_constraint("uq_vault_secret_name_agent", "vault_secrets", type_="unique")
    op.create_unique_constraint(
        "uq_vault_secret_name_agent_org",
        "vault_secrets",
        ["org_id", "name", "agent_id"],
    )


def downgrade() -> None:
    # vault_secrets
    op.drop_constraint("uq_vault_secret_name_agent_org", "vault_secrets", type_="unique")
    op.create_unique_constraint(
        "uq_vault_secret_name_agent", "vault_secrets", ["name", "agent_id"]
    )
    op.drop_constraint("fk_vault_secrets_org_id", "vault_secrets", type_="foreignkey")
    op.drop_column("vault_secrets", "org_id")

    # mcp_servers
    op.drop_constraint("uq_mcp_server_name_per_org", "mcp_servers", type_="unique")
    op.create_unique_constraint("mcp_servers_name_key", "mcp_servers", ["name"])
    op.drop_constraint("fk_mcp_servers_org_id", "mcp_servers", type_="foreignkey")
    op.drop_column("mcp_servers", "org_id")

    # agents
    op.drop_constraint("fk_agents_org_id", "agents", type_="foreignkey")
    op.drop_column("agents", "org_id")
