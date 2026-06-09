"""
Arbiter — Pydantic schemas for Execution Trace resources.

A "trace" maps 1-to-1 with a Session.  Exposing them as traces gives the
frontend a purpose-built shape for waterfall timeline rendering.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class TraceListItem(BaseModel):
    trace_id: uuid.UUID
    agent_id: uuid.UUID
    agent_name: str
    started_at: datetime
    ended_at: datetime | None
    duration_ms: int | None
    tool_call_count: int
    error_count: int
    status: Literal["active", "failed", "completed"]


class TraceListResponse(BaseModel):
    traces: list[TraceListItem]
    total: int
    page: int
    page_size: int


class TraceStep(BaseModel):
    step: int
    tool_name: str
    mcp_server_name: str | None
    occurred_at: datetime
    duration_ms: int | None
    cache_hit: bool
    status: Literal["ok", "error"]
    error: str | None
    offset_ms: float


class TraceDetailResponse(BaseModel):
    trace_id: uuid.UUID
    agent_id: uuid.UUID
    agent_name: str
    started_at: datetime
    ended_at: datetime | None
    duration_ms: int | None
    status: Literal["active", "failed", "completed"]
    steps: list[TraceStep]
