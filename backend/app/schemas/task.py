"""
Arbiter — Pydantic schemas for Task resources (Mission Control).

Tasks are queued by org owners/admins (JWT auth) and consumed by agents
(API-key auth) through the claim/complete endpoints.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# Allowed values mirrored here so the API validates them — DB still stores strings
# so the constraint travels with the schema, not the table.
_VALID_PRIORITIES = ("low", "normal", "high")
_VALID_STATUS_REPORTS = ("done", "failed")


class TaskCreate(BaseModel):
    """Body for POST /tasks — queued by org owner/admin."""

    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    priority: Literal["low", "normal", "high"] = "normal"


class TaskCompleteRequest(BaseModel):
    """
    Body for PATCH /tasks/{id}/complete — agent reports the outcome.

    Defaults to status="done"; pass status="failed" to mark a failure.
    """

    output: str | None = None
    status: Literal["done", "failed"] = "done"


class TaskResponse(BaseModel):
    """Response schema for a Task resource."""

    id: uuid.UUID
    title: str
    description: str | None
    status: str
    priority: str
    claimed_by_agent_id: uuid.UUID | None
    output: str | None
    created_at: datetime
    claimed_at: datetime | None
    completed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
