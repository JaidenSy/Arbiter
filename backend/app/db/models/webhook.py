"""
Arbiter SQLAlchemy ORM models: Webhook and WebhookDeliveryLog.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    pass


WEBHOOK_EVENTS = frozenset(
    [
        "quota.exceeded",
        "error_rate.spike",
        "mcp_server.offline",
        "permission.denied",
    ]
)


class Webhook(Base):
    """
    A registered webhook endpoint for an org.

    Columns:
        id:         UUID primary key.
        org_id:     FK → organizations.id.
        url:        Destination URL to POST events to.
        secret:     HMAC-SHA256 signing key; sent as X-Arbiter-Signature header.
        events:     JSONB list of subscribed event type strings.
        is_active:  False to temporarily pause delivery without deleting.
        created_at: Insert timestamp.
        updated_at: Last modification timestamp.
    """

    __tablename__ = "webhooks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    secret: Mapped[str] = mapped_column(String(255), nullable=False)
    events: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    delivery_logs: Mapped[list[WebhookDeliveryLog]] = relationship(
        "WebhookDeliveryLog",
        back_populates="webhook",
        cascade="all, delete-orphan",
        order_by="WebhookDeliveryLog.delivered_at.desc()",
    )

    def __repr__(self) -> str:
        return f"<Webhook id={self.id} url={self.url!r}>"


class WebhookDeliveryLog(Base):
    """
    Immutable record of a single webhook delivery attempt.
    """

    __tablename__ = "webhook_delivery_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    webhook_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("webhooks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    response_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    delivered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    webhook: Mapped[Webhook] = relationship("Webhook", back_populates="delivery_logs")

    def __repr__(self) -> str:
        return f"<WebhookDeliveryLog webhook={self.webhook_id} event={self.event_type!r} status={self.response_status}>"
