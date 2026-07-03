"""
Arbiter Pydantic schemas: Analytics.

Response shapes for the per-agent cost attribution endpoint.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel


class AgentTrendPoint(BaseModel):
    date: str        # ISO date: "2026-05-27"
    tool_calls: int


class AgentUsage(BaseModel):
    agent_id: uuid.UUID
    agent_name: str
    tool_calls_this_month: int
    pct_of_org_quota: float   # 0.0 when plan quota is unlimited
    trend: list[AgentTrendPoint]  # 7 entries, oldest → newest


class AgentAnalyticsResponse(BaseModel):
    period: str               # "2026-06"
    agents: list[AgentUsage]  # sorted by tool_calls_this_month DESC
    org_total_this_month: int
    org_quota: int | None     # None = unlimited (enterprise)
