"""
Arbiter — Pydantic schemas for agent risk / anomaly detection.

GET /agents/{id}/risk returns an AgentRiskResponse with a weighted risk score
computed from 5 anomaly-detection signals over the last 7 days of session data.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class AgentRiskSignals(BaseModel):
    """Normalised (0.0–1.0) contribution of each individual anomaly signal."""

    error_rate_spike: float = Field(
        ..., ge=0.0, le=1.0,
        description="1.0 if 24h error rate > 2× 7-day baseline, else 0.0",
    )
    burst_ratio: float = Field(
        ..., ge=0.0, le=1.0,
        description="Calls in last hour vs. 7-day hourly avg, normalised to 0–1",
    )
    novel_tool_count: float = Field(
        ..., ge=0.0, le=1.0,
        description="Tools used in last 24h not seen in prior 6 days, normalised to 0–1 (cap=5)",
    )
    latency_spike_ratio: float = Field(
        ..., ge=0.0, le=1.0,
        description="1.0 if avg latency last 24h > 2× 7-day avg, else 0.0",
    )
    off_hours_ratio_24h: float = Field(
        ..., ge=0.0, le=1.0,
        description="Fraction of last-24h calls outside UTC 06:00–22:00",
    )


class AgentRiskResponse(BaseModel):
    """Response for GET /agents/{id}/risk."""

    agent_id: uuid.UUID
    score: float = Field(..., ge=0.0, le=1.0, description="Weighted risk score (0.0–1.0)")
    level: str = Field(..., description="low | medium | high | critical")
    signals: AgentRiskSignals
