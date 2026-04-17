"""
Nexvault — Pydantic schemas for Agent resources.

Separating request/response schemas from ORM models keeps the API contract
stable even when internal DB columns change.  Raw api_key_hash is never
exposed through these schemas.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class AgentCreate(BaseModel):
    """
    Request body for POST /agents.

    The API key is generated server-side and returned ONCE in AgentCreateResponse.
    Callers supply only the human-readable metadata.
    """

    name: str = Field(..., min_length=1, max_length=255, description="Human-readable agent label")
    description: str | None = Field(None, max_length=1000, description="Optional notes")


class AgentResponse(BaseModel):
    """
    Response body for GET /agents and GET /agents/{id}.

    Never includes the api_key_hash or any sensitive data.
    """

    id: uuid.UUID
    name: str
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AgentCreateResponse(AgentResponse):
    """
    Response body for POST /agents only.

    Includes the raw API key shown exactly ONCE.  The caller must store it;
    it cannot be retrieved again.
    """

    api_key: str = Field(..., description="Raw API key — store this now, it will not be shown again")
