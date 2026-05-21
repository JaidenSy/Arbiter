"""
Arbiter — SQLAlchemy ORM model: CacheEntry.

Stores the results of tool calls for semantic deduplication.  When a new
tool call arrives, the CacheService computes its embedding and searches
for a stored entry whose embedding is within the similarity threshold.
On a hit, the stored response_payload is returned without forwarding to
the MCP server.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CacheEntry(Base):
    """
    A cached tool call result.

    Columns:
        id:               UUID primary key.
        tool_name:        Name of the tool (e.g. "read_file").
        input_hash:       SHA-256 of the canonical (sorted-key) JSON of the input.
                          Used for exact-match lookups before embedding search.
        input_embedding:  Float array from the sentence-transformer model,
                          stored as vector(384) for pgvector ANN search.
                          Used for approximate nearest-neighbour lookup when
                          there is no exact hash match.
        response_payload: Full JSON response from the MCP server.
        hit_count:        Number of times this entry has been served from cache.
        created_at:       When the entry was inserted.
        expires_at:       After this timestamp the entry is considered stale
                          and will be evicted by the background sweeper.
    """

    __tablename__ = "cache_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
    )
    tool_name: Mapped[str] = mapped_column(String(255), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    input_embedding: Mapped[list[float] | None] = mapped_column(Vector(384), nullable=True)
    response_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    hit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    # ── Composite unique constraint: exact-match path ─────────────────────────
    # Defined in schema.sql via UNIQUE (tool_name, input_hash)

    def __repr__(self) -> str:
        return (
            f"<CacheEntry id={self.id} tool={self.tool_name!r} "
            f"hits={self.hit_count} expires={self.expires_at}>"
        )
