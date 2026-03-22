"""
NexusAI — API endpoints: Stats.

Dashboard statistics endpoint returning aggregated counts and metrics.

Routes:
    GET    /stats     — return agents_count, servers_count, tool_calls_today,
                        cache_hit_rate_today
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_agent, get_db
from app.db.models.agent import Agent
from app.db.models.mcp_server import MCPServer
from app.db.models.session import SessionEvent

router = APIRouter(prefix="/stats", tags=["stats"])


# ── Schema ────────────────────────────────────────────────────────────────────


class StatsResponse(BaseModel):
    """Dashboard statistics snapshot."""

    agents_count: int
    servers_count: int
    tool_calls_today: int
    cache_hit_rate_today: float  # 0.0–1.0


# ── Endpoint ──────────────────────────────────────────────────────────────────


@router.get(
    "",
    response_model=StatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get dashboard statistics",
)
async def get_stats(
    db: AsyncSession = Depends(get_db),
    _current: Agent = Depends(get_current_agent),
) -> StatsResponse:
    """
    Return a snapshot of key gateway metrics for dashboard display.

    Metrics are computed inline per request.  For high-traffic deployments
    consider caching this response in Redis with a short TTL.

    Stats included:
        - agents_count:         Number of currently active agents.
        - servers_count:        Number of currently active MCP servers.
        - tool_calls_today:     Total tool calls (session events) since UTC midnight.
        - cache_hit_rate_today: Fraction of today's calls served from cache (0.0–1.0).
                                Returns 0.0 when there are no calls today.

    Args:
        db:       Injected DB session.
        _current: Auth guard — valid API key required.

    Returns:
        StatsResponse: Aggregated dashboard statistics.
    """
    # ── Active agents count ────────────────────────────────────────────────────
    agents_result = await db.execute(select(func.count(Agent.id)).where(Agent.is_active.is_(True)))
    agents_count: int = agents_result.scalar_one() or 0

    # ── Active MCP servers count ───────────────────────────────────────────────
    servers_result = await db.execute(
        select(func.count(MCPServer.id)).where(MCPServer.is_active.is_(True))
    )
    servers_count: int = servers_result.scalar_one() or 0

    # ── Today's tool calls and cache hit rate ──────────────────────────────────
    # DATE_TRUNC('day', NOW()) truncates to UTC midnight.
    today_midnight = func.date_trunc("day", func.now())

    calls_result = await db.execute(
        select(
            func.count(SessionEvent.id).label("total"),
            func.sum(case((SessionEvent.cache_hit.is_(True), 1), else_=0)).label("hits"),
        ).where(SessionEvent.occurred_at >= today_midnight)
    )
    row = calls_result.one()
    tool_calls_today: int = row.total or 0
    hits_today: int = row.hits or 0

    cache_hit_rate_today: float = hits_today / tool_calls_today if tool_calls_today > 0 else 0.0

    return StatsResponse(
        agents_count=agents_count,
        servers_count=servers_count,
        tool_calls_today=tool_calls_today,
        cache_hit_rate_today=cache_hit_rate_today,
    )
