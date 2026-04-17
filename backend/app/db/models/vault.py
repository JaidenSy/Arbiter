"""
Nexvault — SQLAlchemy ORM model: VaultSecret.

Stores encrypted secrets that the proxy can inject into MCP tool calls at
runtime.  The ciphertext is AES-256-GCM encrypted using the key from
VAULT_ENCRYPTION_KEY env var.  The raw secret is never persisted.

Typical use:
    - Store a GitHub PAT as "GITHUB_TOKEN"
    - When an agent calls a tool, VaultService.get_secret("GITHUB_TOKEN")
      decrypts it on-the-fly and injects it into the request headers.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.agent import Agent


class VaultSecret(Base):
    """
    An AES-256-GCM encrypted secret stored in the database.

    Columns:
        id:          UUID primary key.
        org_id:      FK → organizations.id.
        name:        Logical key used to retrieve the secret (e.g. "GITHUB_TOKEN").
                     Must be unique within (org_id, agent_id).
        ciphertext:  Base64-encoded AES-256-GCM ciphertext (nonce prepended).
        agent_id:    Optional FK to the agent that owns this secret.
                     NULL means it is an org-level secret accessible by any agent
                     in the org (subject to RBAC).
        created_at:  Immutable insert timestamp.
        updated_at:  Auto-updated on every modification (e.g. secret rotation).
    """

    __tablename__ = "vault_secrets"
    __table_args__ = (
        UniqueConstraint("org_id", "name", "agent_id", name="uq_vault_secret_name_agent_org"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    agent: Mapped["Agent | None"] = relationship("Agent", back_populates="vault_secrets")

    def __repr__(self) -> str:
        return f"<VaultSecret id={self.id} name={self.name!r} agent_id={self.agent_id}>"
