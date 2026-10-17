"""
Arbiter SQLAlchemy ORM model: ToolDefinition.

Pins each upstream tool's definition so a server cannot silently change what
a tool says it does after it was approved (the MCP "rug pull", OWASP MCP03).

One row per (mcp_server_id, tool_name).  The first definition seen is trusted
on first use and becomes the approved pin.  A later tools/list whose hash
differs flips the row to ``status = 'changed'`` until an org admin approves
the new definition via the REST API.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

TOOL_STATUS_APPROVED = "approved"
TOOL_STATUS_CHANGED = "changed"

TOOL_CHANGE_POLICY_ALLOW = "allow"
TOOL_CHANGE_POLICY_BLOCK = "block"
TOOL_CHANGE_POLICIES = frozenset([TOOL_CHANGE_POLICY_ALLOW, TOOL_CHANGE_POLICY_BLOCK])


class ToolDefinition(Base):
    """
    Pinned definition of one upstream MCP tool.

    Columns:
        approved_hash:       SHA-256 of the canonical JSON of the approved
                             {name, description, inputSchema}.
        approved_definition: The full tool dict as approved (annotations are
                             read from here, never from an unapproved change).
        current_hash:        Hash of the most recently seen definition.
        current_definition:  Most recently seen tool dict.
        status:              'approved' or 'changed' (pending re-approval).
    """

    __tablename__ = "tool_definitions"
    __table_args__ = (
        UniqueConstraint("mcp_server_id", "tool_name", name="uq_tool_definitions_server_tool"),
        CheckConstraint("status IN ('approved', 'changed')", name="ck_tool_definitions_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    mcp_server_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mcp_servers.id", ondelete="CASCADE"),
        nullable=False,
    )
    tool_name: Mapped[str] = mapped_column(String(255), nullable=False)
    approved_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    approved_definition: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    current_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    current_definition: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=TOOL_STATUS_APPROVED, server_default="approved"
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    def __repr__(self) -> str:
        return (
            f"<ToolDefinition server={self.mcp_server_id} tool={self.tool_name!r} "
            f"status={self.status!r}>"
        )
