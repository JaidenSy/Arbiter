"""
Arbiter — SQLAlchemy ORM model: Task.

A Task is a unit of work an org owner/admin queues for their agents.  Agents
poll the queue, claim a pending task, work it, and report completion (or
failure) back via the Mission Control API.  This powers the Mission Control
dashboard's task board.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.agent import Agent


class Task(Base):
    """
    A unit of agent-executable work queued by an org owner/admin.

    Lifecycle:
        pending  → an admin queued it; no agent has claimed it yet.
        claimed  → an agent picked it up; ``claimed_by_agent_id`` set.
        done     → agent reported success; ``output`` and ``completed_at`` set.
        failed   → agent reported failure; ``output`` carries the failure note.

    Columns:
        id:                    Auto-generated UUID primary key.
        org_id:                FK → organizations.id (CASCADE on delete).
        title:                 Short human-readable summary.
        description:           Optional longer-form brief for the agent.
        status:                pending | claimed | done | failed.
        priority:              low | normal | high — purely advisory.
        claimed_by_agent_id:   FK → agents.id (SET NULL); set on claim.
        output:                Agent-reported result (success notes or failure reason).
        created_at:            When the task was queued.
        claimed_at:            When an agent claimed the task.
        completed_at:          When the task entered done/failed.
    """

    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
    )
    priority: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="normal",
    )
    claimed_by_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="SET NULL"),
        nullable=True,
    )
    output: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    claimed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    claimed_by_agent: Mapped["Agent | None"] = relationship("Agent")

    # ── Indexes ───────────────────────────────────────────────────────────────
    __table_args__ = (
        # Queue polling: list pending tasks in an org, ordered by creation.
        Index("ix_tasks_org_status", "org_id", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<Task id={self.id} title={self.title!r} "
            f"status={self.status} priority={self.priority}>"
        )
