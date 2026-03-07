"""
NexusAI — SQLAlchemy ORM model: MCPServer.

An MCPServer is a registered Model Context Protocol server that the gateway
can forward tool calls to.  Access is controlled via the tool_permissions
RBAC table.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MCPServer(Base):
    """
    Registered MCP server reachable through the NexusAI proxy.

    Columns:
        id:          Auto-generated UUID primary key.
        name:        Unique slug used in permission rules (e.g. "filesystem").
        base_url:    Full HTTP(S) URL of the MCP server.
        description: Optional notes about the server's capabilities.
        is_active:   Soft-delete; inactive servers reject all forwarded calls.
        created_at:  Immutable insert timestamp.
        updated_at:  Auto-updated on every modification.
    """

    __tablename__ = "mcp_servers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    base_url: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
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

    def __repr__(self) -> str:
        return f"<MCPServer id={self.id} name={self.name!r} url={self.base_url!r}>"
