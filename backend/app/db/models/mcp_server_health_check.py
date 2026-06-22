"""
Arbiter SQLAlchemy ORM model: MCPServerHealthCheck.

Records the result of each automated health probe sent to a registered MCP server.
Used by the circuit breaker to deactivate servers with persistent failures and by
the dashboard to surface uptime %.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MCPServerHealthCheck(Base):
    """
    A single health-probe result for an MCP server.

    Columns:
        id:          UUID primary key.
        server_id:   FK → mcp_servers.id (SET NULL if the server is deleted).
        org_id:      FK → organizations.id (CASCADE delete).
        is_healthy:  True = tools/list succeeded; False = timed out or errored.
        latency_ms:  Round-trip time in milliseconds (NULL on failure).
        error:       Error message (NULL on success).
        checked_at:  UTC timestamp of this probe.
    """

    __tablename__ = "mcp_server_health_checks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    server_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mcp_servers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    is_healthy: Mapped[bool] = mapped_column(Boolean, nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return (
            f"<MCPServerHealthCheck server_id={self.server_id} "
            f"healthy={self.is_healthy} checked_at={self.checked_at}>"
        )
