"""
Arbiter SQLAlchemy ORM models: Session and SessionEvent.

A Session groups related tool calls made by a single agent within one
context window.  Each proxied tool call is recorded as an immutable
SessionEvent for auditing and replay.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.agent import Agent
    from app.db.models.mcp_server import MCPServer
    from app.db.models.user import User


class Session(Base):
    """
    A logical grouping of tool calls by one agent.

    Columns:
        id:                Auto-generated UUID primary key.
        org_id:            FK → organizations.id (denormalized for fast org-scoped queries).
        agent_id:          FK → agents.id.
        parent_session_id: FK → sessions.id: set when this session was spawned by another
                           agent's tool call (multi-hop agent chain).
        trace_id:          UUID shared by all sessions in the same call chain.
                           Root sessions have trace_id == id.
        started_at:        When the session was opened.
        ended_at:          When the session was closed (NULL = still active).
        metadata:          Arbitrary JSON blob for caller-supplied context.
    """

    __tablename__ = "sessions"

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
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
    )
    parent_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    trace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        default=uuid.uuid4,
        index=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    agent: Mapped[Agent] = relationship("Agent", back_populates="sessions")
    events: Mapped[list[SessionEvent]] = relationship(
        "SessionEvent",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="SessionEvent.occurred_at",
    )
    children: Mapped[list[Session]] = relationship(
        "Session",
        foreign_keys="Session.parent_session_id",
        back_populates="parent",
        lazy="select",
    )
    parent: Mapped[Session | None] = relationship(
        "Session",
        foreign_keys="Session.parent_session_id",
        back_populates="children",
        remote_side="Session.id",
    )

    __table_args__ = (Index("ix_sessions_trace_id_org_id", "trace_id", "org_id"),)

    def __repr__(self) -> str:
        return f"<Session id={self.id} agent_id={self.agent_id}>"


class SessionEvent(Base):
    """
    Immutable audit record of a single proxied tool call.

    Columns:
        id:               UUID primary key.
        org_id:           FK → organizations.id (denormalized for fast org audit queries).
        session_id:       FK → sessions.id.
        mcp_server_id:    FK → mcp_servers.id (nullable: server may be deleted).
        tool_name:        Name of the tool that was called.
        request_payload:  Full JSON body sent to the MCP server.
        response_payload: Full JSON body received back (NULL on error).
        cache_hit:        True when the response was served from cache.
        duration_ms:      Round-trip time in milliseconds.
        error:            Error message if the call failed.
        occurred_at:      Immutable timestamp of the call.
    """

    __tablename__ = "session_events"

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
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    mcp_server_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mcp_servers.id", ondelete="SET NULL"),
        nullable=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    tool_name: Mapped[str] = mapped_column(String(255), nullable=False)
    request_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    response_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    cache_hit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(
        Numeric(precision=12, scale=6),
        nullable=True,
        comment="Cost in USD; NULL when server has no cost configured or call was a cache hit",
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    session: Mapped[Session] = relationship("Session", back_populates="events")
    mcp_server: Mapped[MCPServer | None] = relationship("MCPServer")
    user: Mapped[User | None] = relationship("User")

    def __repr__(self) -> str:
        return f"<SessionEvent id={self.id} tool={self.tool_name!r} cache_hit={self.cache_hit}>"
