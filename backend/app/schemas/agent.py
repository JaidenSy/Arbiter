"""
Arbiter — Pydantic schemas for Agent resources.

Separating request/response schemas from ORM models keeps the API contract
stable even when internal DB columns change.  Raw api_key_hash is never
exposed through these schemas.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

_VALID_SCOPES = {"full", "read_only", "vault_read_only"}


class AgentCreate(BaseModel):
    """
    Request body for POST /agents.

    The API key is generated server-side and returned ONCE in AgentCreateResponse.
    Callers supply only the human-readable metadata.
    """

    name: str = Field(..., min_length=1, max_length=255, description="Human-readable agent label")
    description: str | None = Field(None, max_length=1000, description="Optional notes")
    scope: str = Field(
        "full",
        description="Permission scope: 'full', 'read_only' (no vault writes), or 'vault_read_only' (no tool calls)",
    )
    rate_limit_per_minute: int | None = Field(
        None,
        ge=1,
        description="Max total tool calls per minute across all tools. Null = unlimited.",
    )
    max_calls_per_session: int | None = Field(
        None,
        ge=1,
        description="Max tool calls allowed per session. Null = unlimited.",
    )


class AgentResponse(BaseModel):
    """
    Response body for GET /agents and GET /agents/{id}.

    Never includes the api_key_hash or any sensitive data.
    """

    id: uuid.UUID
    name: str
    description: str | None
    is_active: bool
    scope: str
    rate_limit_per_minute: int | None
    max_calls_per_session: int | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AgentUpdate(BaseModel):
    """Request body for PATCH /agents/{id} — all fields optional."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=1000)
    rate_limit_per_minute: int | None = Field(None, ge=1)
    max_calls_per_session: int | None = Field(None, ge=1)


class AgentCreateResponse(AgentResponse):
    """
    Response body for POST /agents only.

    Includes the raw API key shown exactly ONCE.  The caller must store it;
    it cannot be retrieved again.
    """

    api_key: str = Field(
        ..., description="Raw API key — store this now, it will not be shown again"
    )
