"""
NexVault — SQLAlchemy ORM model: ToolPermission.

Join table that enforces which agent may call which tool on which MCP server.
The wildcard tool_name ``"*"`` grants access to all tools on the server.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ToolPermission(Base):
    """
    RBAC permission record: (agent, mcp_server, tool_name).

    Columns:
        id:                  UUID primary key.
        org_id:              FK → organizations.id (denormalized for fast org-scoped queries).
        agent_id:            FK → agents.id (cascades on delete).
        mcp_server_id:       FK → mcp_servers.id (cascades on delete).
        tool_name:           Exact tool name or ``"*"`` wildcard.
        granted_at:          Immutable insert timestamp.
        granted_by:          Free-text approver identifier (legacy field).
        granted_by_user_id:  FK → users.id — human user who granted permission.
    """

    __tablename__ = "tool_permissions"
    __table_args__ = (
        UniqueConstraint("agent_id", "mcp_server_id", "tool_name", name="uq_tool_permission"),
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
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
    )
    mcp_server_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mcp_servers.id", ondelete="CASCADE"),
        nullable=False,
    )
    tool_name: Mapped[str] = mapped_column(String(255), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    granted_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    granted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    rate_limit_per_minute: Mapped[int | None] = mapped_column(Integer, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<ToolPermission agent={self.agent_id} "
            f"server={self.mcp_server_id} tool={self.tool_name!r}>"
        )
