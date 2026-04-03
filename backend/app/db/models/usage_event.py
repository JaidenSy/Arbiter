"""
NexusAI — SQLAlchemy ORM model: UsageEvent.

One row per org per calendar day.  Counters are incremented via an upsert
so the proxy hot path can fire-and-forget without a read-modify-write cycle.

Upsert pattern:
    INSERT INTO usage_events (org_id, event_date, tool_calls)
    VALUES ($1, CURRENT_DATE, 1)
    ON CONFLICT (org_id, event_date)
    DO UPDATE SET tool_calls = usage_events.tool_calls + EXCLUDED.tool_calls;
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UsageEvent(Base):
    """
    Daily usage counters per organization.

    Columns:
        id:              Auto-generated UUID primary key.
        org_id:          FK → organizations.id.
        event_date:      Calendar date (UTC).  Combined with org_id as unique key.
        tool_calls:      Number of proxied tool calls on this date.
        cache_hits:      Number of those calls served from cache.
        vault_reads:     Number of vault secret decryptions.
        agents_created:  Number of new agents registered.
        created_at:      First-insert timestamp (informational).
    """

    __tablename__ = "usage_events"
    __table_args__ = (
        UniqueConstraint("org_id", "event_date", name="uq_usage_events_org_date"),
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
    event_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        server_default=func.current_date(),
    )
    tool_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_hits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    vault_reads: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    agents_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return (
            f"<UsageEvent org={self.org_id} date={self.event_date} "
            f"tool_calls={self.tool_calls}>"
        )
