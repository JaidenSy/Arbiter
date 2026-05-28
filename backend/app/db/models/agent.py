"""
Arbiter — SQLAlchemy ORM model: Agent.

An Agent represents an AI assistant (Claude instance, automation script,
etc.) that authenticates to the Arbiter gateway with an API key and is
subject to RBAC-controlled tool access.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.session import Session
    from app.db.models.vault import VaultSecret


class Agent(Base):
    """
    Persistent record of an agent registered with the gateway.

    Columns:
        id:            Auto-generated UUID primary key.
        org_id:        FK → organizations.id.  Agent belongs to exactly one org.
        name:          Human-readable label (e.g. "Claude-prod").
        description:   Optional notes about this agent's purpose.
        api_key_hash:  SHA-256 hash of the raw API key — never the raw key.
        is_active:     Soft-delete flag; inactive agents are rejected at auth.
        created_at:    Timestamp set on INSERT, never modified.
        updated_at:    Timestamp updated on every UPDATE via DB trigger.
    """

    __tablename__ = "agents"

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
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Scope controls what this agent's key can do:
    #   "full"           — call tools, read/write vault secrets, manage sessions
    #   "read_only"      — tool calls only, no vault writes or secret reads
    #   "vault_read_only"— only allowed to read vault secrets, no tool calls
    scope: Mapped[str] = mapped_column(String(32), nullable=False, default="full")
    rate_limit_per_minute: Mapped[int | None] = mapped_column(Integer, nullable=True)
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
    sessions: Mapped[list["Session"]] = relationship(
        "Session",
        back_populates="agent",
        cascade="all, delete-orphan",
    )
    vault_secrets: Mapped[list["VaultSecret"]] = relationship(
        "VaultSecret",
        back_populates="agent",
    )

    def __repr__(self) -> str:
        return f"<Agent id={self.id} name={self.name!r} active={self.is_active}>"
