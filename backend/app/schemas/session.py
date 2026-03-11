"""
NexusAI — Pydantic schemas for Session and SessionEvent resources.

Sessions are read-only from the API perspective — they are opened and
closed by the proxy service automatically.  Clients can query them for
audit and debugging.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SessionEventResponse(BaseModel):
    """
    Response schema for a single audit event within a session.

    request_payload and response_payload are arbitrary JSON dicts matching
    the MCP protocol.  error is populated only on failed calls.
    """

    id: uuid.UUID
    session_id: uuid.UUID
    mcp_server_id: uuid.UUID | None
    tool_name: str
    request_payload: dict[str, Any]
    response_payload: dict[str, Any] | None
    cache_hit: bool
    duration_ms: int | None
    error: str | None
    occurred_at: datetime

    model_config = {"from_attributes": True}


class SessionResponse(BaseModel):
    """
    Response schema for a Session resource.

    events is omitted from list responses (included only in GET /sessions/{id}).
    """

    id: uuid.UUID
    agent_id: uuid.UUID
    started_at: datetime
    ended_at: datetime | None
    metadata: dict[str, Any] = Field(default_factory=dict, alias="metadata_")
    events: list[SessionEventResponse] = Field(default_factory=list)

    model_config = {"populate_by_name": True, "from_attributes": True}
