"""
NexusAI — Pydantic schemas for the Proxy (tool call gateway) endpoint.

These schemas define the public contract for POST /proxy/tool-call — the
central gateway endpoint that agents call to invoke MCP tools.
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field


class ToolCallRequest(BaseModel):
    """
    Request body for POST /proxy/tool-call.

    The agent specifies which MCP server and tool to call, plus the
    arguments dict.  The gateway handles auth, RBAC, caching, and
    secret injection transparently.
    """

    server_name: str = Field(
        ...,
        description="Logical name of the MCP server (matches mcp_servers.name)",
    )
    tool_name: str = Field(
        ...,
        description="Name of the tool to invoke on the MCP server",
    )
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Tool arguments dict. String values may use {{SECRET_NAME}} placeholders.",
    )
    session_id: uuid.UUID | None = Field(
        None,
        description="Optional session UUID. If omitted a new session is created.",
    )


class ToolCallResponse(BaseModel):
    """
    Response body for POST /proxy/tool-call.

    Always includes the result payload and metadata about how the request
    was served (cache hit, latency, session).
    """

    session_id: uuid.UUID = Field(..., description="Session this call was recorded under")
    event_id: uuid.UUID = Field(..., description="Audit event UUID for this specific call")
    tool_name: str
    result: dict[str, Any] = Field(..., description="Raw response payload from the MCP server")
    cache_hit: bool = Field(..., description="True if the result was served from semantic cache")
    duration_ms: int | None = Field(None, description="Total round-trip time in milliseconds")
