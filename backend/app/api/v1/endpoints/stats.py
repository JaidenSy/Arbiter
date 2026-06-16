"""
Arbiter — API endpoints: Stats.

Dashboard statistics endpoint returning aggregated counts and metrics.

Routes:
    GET    /stats              — return agents_count, servers_count, tool_calls_today,
                                 cache_hit_rate_today, latency_p50/p95/p99, slowest_tools
    GET    /stats/usage/summary — monthly tool call usage + plan limit
    GET    /stats/history      — historical time-series bucketed by hour (24h) or day (7d)

All endpoints accept optional ?agent_id=<uuid> and ?server_name=<str> filters.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import case, func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.db.models.agent import Agent
from app.db.models.mcp_server import MCPServer
from app.db.models.organization import Organization
from app.db.models.session import Session, SessionEvent
from app.db.models.usage_event import UsageEvent
from app.db.models.user import User
from app.services.plan.plan_limits import PAID_TIERS, PLAN_LIMITS

router = APIRouter(prefix="/stats", tags=["stats"])


# ── Schema ────────────────────────────────────────────────────────────────────


class SlowTool(BaseModel):
    """A slow tool entry in the Dashboard stats response."""

    tool_name: str
    server_name: str | None
    avg_duration_ms: float
    call_count: int


class StatsResponse(BaseModel):
    """Dashboard statistics snapshot."""

    agents_count: int
    servers_count: int
    tool_calls_today: int
    cache_hit_rate_today: float  # 0.0–1.0
    error_rate_today: float  # 0.0–1.0
    latency_p50_ms: float | None
    latency_p95_ms: float | None
    latency_p99_ms: float | None
    slowest_tools: list[SlowTool]


class HistoryBucket(BaseModel):
    """A single time bucket of aggregated activity metrics."""

    timestamp: str  # ISO format — hour start for 24h, day start for 7d
    label: str  # "14:00" for 24h, "Mon" / "Tue" etc. for 7d
    tool_calls: int
    cache_hits: int
    cache_hit_rate: float  # 0.0–1.0, 0.0 if no calls
    errors: int


class StatsHistoryResponse(BaseModel):
    """Historical time-series data for the dashboard chart."""

    period: str
    buckets: list[HistoryBucket]


class UsageSummaryResponse(BaseModel):
    """Monthly usage summary for the usage strip and dashboard quota card."""

    tool_calls_month: int
    tool_calls_month_limit: int | None  # None = unlimited (enterprise)


class CostBreakdownItem(BaseModel):
    name: str
    cost_usd: float


class CostStatsResponse(BaseModel):
    """Monthly cost summary for Pro/Enterprise orgs."""

    cost_this_month_usd: float
    cost_saved_by_cache_usd: float
    by_agent: list[CostBreakdownItem]
    by_server: list[CostBreakdownItem]


# ── Helpers ───────────────────────────────────────────────────────────────────


def _se_filters(
    org_id: uuid.UUID,
    agent_id: uuid.UUID | None,
    server_name: str | None,
) -> list[Any]:
    """Return SessionEvent WHERE clauses scoped to org, optionally filtered by agent/server."""
    filters: list[Any] = [SessionEvent.org_id == org_id]
    if agent_id is not None:
        agent_sessions = (
            select(Session.id)
            .where(Session.agent_id == agent_id, Session.org_id == org_id)
            .scalar_subquery()
        )
        filters.append(SessionEvent.session_id.in_(agent_sessions))
    if server_name is not None:
        server_ids = (
            select(MCPServer.id)
            .where(MCPServer.name == server_name, MCPServer.org_id == org_id)
            .scalar_subquery()
        )
        filters.append(SessionEvent.mcp_server_id.in_(server_ids))
    return filters


# ── Endpoint ──────────────────────────────────────────────────────────────────


@router.get(
    "",
    response_model=StatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get dashboard statistics",
)
async def get_stats(
    agent_id: uuid.UUID | None = Query(None, description="Filter metrics to this agent"),
    server_name: str | None = Query(None, description="Filter metrics to this MCP server name"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StatsResponse:
    """
    Return a snapshot of key gateway metrics for dashboard display.

    Metrics are computed inline per request.  For high-traffic deployments
    consider caching this response in Redis with a short TTL.

    Stats included:
        - agents_count:         Number of currently active agents (org-wide).
        - servers_count:        Number of currently active MCP servers (org-wide).
        - tool_calls_today:     Total tool calls since UTC midnight (filterable).
        - cache_hit_rate_today: Fraction of today's calls served from cache (filterable).
        - error_rate_today:     Fraction of today's calls that errored (filterable).
        - latency_p50/p95/p99: Percentile latencies for today's calls (filterable).
        - slowest_tools:        Top 5 slowest tools by avg duration today (filterable).
    """
    # ── Active agents count (org-wide, not filterable) ────────────────────────
    agents_result = await db.execute(
        select(func.count(Agent.id)).where(
            Agent.is_active.is_(True), Agent.org_id == current_user.org_id
        )
    )
    agents_count: int = agents_result.scalar_one() or 0

    # ── Active MCP servers count (org-wide, not filterable) ───────────────────
    servers_result = await db.execute(
        select(func.count(MCPServer.id)).where(
            MCPServer.is_active.is_(True), MCPServer.org_id == current_user.org_id
        )
    )
    servers_count: int = servers_result.scalar_one() or 0

    # ── Build filtered WHERE clauses for today's session events ───────────────
    today_midnight = func.date_trunc("day", func.now())
    base_filters = _se_filters(current_user.org_id, agent_id, server_name)
    today_filters = [*base_filters, SessionEvent.occurred_at >= today_midnight]

    # ── Today's tool calls, cache hits, errors ────────────────────────────────
    calls_result = await db.execute(
        select(
            func.count(SessionEvent.id).label("total"),
            func.sum(case((SessionEvent.cache_hit.is_(True), 1), else_=0)).label("hits"),
            func.sum(case((SessionEvent.error.isnot(None), 1), else_=0)).label("errors"),
        ).where(*today_filters)
    )
    row = calls_result.one()
    tool_calls_today: int = row.total or 0
    hits_today: int = row.hits or 0
    errors_today: int = row.errors or 0

    cache_hit_rate_today: float = hits_today / tool_calls_today if tool_calls_today > 0 else 0.0
    error_rate_today: float = errors_today / tool_calls_today if tool_calls_today > 0 else 0.0

    # ── Latency percentiles (p50/p95/p99) for today ───────────────────────────
    latency_result = await db.execute(
        select(
            func.percentile_cont(0.50).within_group(SessionEvent.duration_ms).label("p50"),
            func.percentile_cont(0.95).within_group(SessionEvent.duration_ms).label("p95"),
            func.percentile_cont(0.99).within_group(SessionEvent.duration_ms).label("p99"),
        ).where(*today_filters, SessionEvent.duration_ms.isnot(None))
    )
    lat_row = latency_result.one_or_none()
    latency_p50: float | None = float(lat_row.p50) if lat_row and lat_row.p50 is not None else None
    latency_p95: float | None = float(lat_row.p95) if lat_row and lat_row.p95 is not None else None
    latency_p99: float | None = float(lat_row.p99) if lat_row and lat_row.p99 is not None else None

    # ── Slowest tools (top 5 by avg duration today) ───────────────────────────
    slowest_result = await db.execute(
        select(
            SessionEvent.tool_name,
            MCPServer.name.label("server_name"),
            func.avg(SessionEvent.duration_ms).label("avg_ms"),
            func.count(SessionEvent.id).label("cnt"),
        )
        .outerjoin(MCPServer, SessionEvent.mcp_server_id == MCPServer.id)
        .where(*today_filters, SessionEvent.duration_ms.isnot(None))
        .group_by(SessionEvent.tool_name, MCPServer.name)
        .order_by(func.avg(SessionEvent.duration_ms).desc())
        .limit(5)
    )
    slowest_tools = [
        SlowTool(
            tool_name=r.tool_name,
            server_name=r.server_name,
            avg_duration_ms=round(float(r.avg_ms), 1),
            call_count=int(r.cnt),
        )
        for r in slowest_result.all()
    ]

    return StatsResponse(
        agents_count=agents_count,
        servers_count=servers_count,
        tool_calls_today=tool_calls_today,
        cache_hit_rate_today=cache_hit_rate_today,
        error_rate_today=error_rate_today,
        latency_p50_ms=latency_p50,
        latency_p95_ms=latency_p95,
        latency_p99_ms=latency_p99,
        slowest_tools=slowest_tools,
    )


# ── Usage summary endpoint ────────────────────────────────────────────────────


@router.get(
    "/usage/summary",
    response_model=UsageSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get monthly usage summary",
)
async def get_usage_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UsageSummaryResponse:
    """
    Return the total tool calls for the current calendar month plus the plan limit.

    Reads from the usage_events table which is updated via upsert on each
    proxied tool call.  Returns 0 when no events exist for the month yet.
    The limit is derived from the org's current plan_tier via PLAN_LIMITS;
    None means unlimited (enterprise).
    """
    month_start = func.date_trunc("month", func.now())
    result = await db.execute(
        select(func.coalesce(func.sum(UsageEvent.tool_calls), 0).label("total")).where(
            UsageEvent.org_id == current_user.org_id,
            UsageEvent.event_date >= month_start,
        )
    )
    total: int = result.scalar_one() or 0

    # Load org to resolve plan-tier limit.
    org = await db.get(Organization, current_user.org_id)
    plan_tier = org.plan_tier if org else "free"
    limit: int | None = PLAN_LIMITS.get(plan_tier, {}).get("max_tool_calls_mo")

    return UsageSummaryResponse(tool_calls_month=total, tool_calls_month_limit=limit)


# ── History endpoint ──────────────────────────────────────────────────────────


@router.get(
    "/history",
    response_model=StatsHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get historical activity stats",
)
async def get_stats_history(
    period: str = Query(
        "7d", description="Time period: '7d' (daily buckets) or '24h' (hourly buckets)"
    ),
    agent_id: uuid.UUID | None = Query(None, description="Filter to this agent"),
    server_name: str | None = Query(None, description="Filter to this MCP server name"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StatsHistoryResponse:
    """
    Return historical time-series activity data for the dashboard chart.

    For period='7d': 7 daily buckets (one per day, oldest first).
    For period='24h': 24 hourly buckets (one per hour, oldest first).
    Buckets with no events are filled with zeros.
    Optional ?agent_id and ?server_name filters scope all counts to a single agent/server.
    """

    if period not in ("7d", "24h"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="period must be '7d' or '24h'",
        )

    now = datetime.now(UTC)
    base_filters = _se_filters(current_user.org_id, agent_id, server_name)

    if period == "7d":
        cutoff = now - timedelta(days=7)
        day_bucket = literal_column("date_trunc('day', session_events.occurred_at)")
        result = await db.execute(
            select(
                day_bucket.label("bucket"),
                func.count().label("total"),
                func.sum(case((SessionEvent.cache_hit.is_(True), 1), else_=0)).label("hits"),
                func.sum(case((SessionEvent.error.isnot(None), 1), else_=0)).label("errors"),
            )
            .where(*base_filters, SessionEvent.occurred_at >= cutoff)
            .group_by(day_bucket)
            .order_by(day_bucket)
        )
        rows = result.all()

        data_by_key: dict[str, object] = {}
        for row in rows:
            day_key = row.bucket.date().isoformat()
            data_by_key[day_key] = row

        buckets: list[HistoryBucket] = []
        for i in range(6, -1, -1):
            day = (now - timedelta(days=i)).date()
            key = day.isoformat()
            row = data_by_key.get(key)  # type: ignore[assignment]
            total = int(row.total) if row else 0
            hits = int(row.hits or 0) if row else 0
            errors = int(row.errors or 0) if row else 0
            bucket_dt = datetime.combine(day, datetime.min.time()).replace(tzinfo=UTC)
            buckets.append(
                HistoryBucket(
                    timestamp=bucket_dt.isoformat(),
                    label=day.strftime("%a"),
                    tool_calls=total,
                    cache_hits=hits,
                    cache_hit_rate=round(hits / total, 3) if total > 0 else 0.0,
                    errors=errors,
                )
            )

    else:  # 24h
        cutoff = now - timedelta(hours=24)
        hour_bucket = literal_column("date_trunc('hour', session_events.occurred_at)")
        result = await db.execute(
            select(
                hour_bucket.label("bucket"),
                func.count().label("total"),
                func.sum(case((SessionEvent.cache_hit.is_(True), 1), else_=0)).label("hits"),
                func.sum(case((SessionEvent.error.isnot(None), 1), else_=0)).label("errors"),
            )
            .where(*base_filters, SessionEvent.occurred_at >= cutoff)
            .group_by(hour_bucket)
            .order_by(hour_bucket)
        )
        rows = result.all()

        data_by_key = {}
        for row in rows:
            hour_dt = row.bucket.replace(minute=0, second=0, microsecond=0)
            if hour_dt.tzinfo is None:
                hour_dt = hour_dt.replace(tzinfo=UTC)
            hour_key = hour_dt.strftime("%Y-%m-%dT%H")
            data_by_key[hour_key] = row

        buckets = []
        start_hour = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=23)
        for i in range(24):
            hour_dt = start_hour + timedelta(hours=i)
            hour_key = hour_dt.strftime("%Y-%m-%dT%H")
            row = data_by_key.get(hour_key)  # type: ignore[assignment]
            total = int(row.total) if row else 0
            hits = int(row.hits or 0) if row else 0
            errors = int(row.errors or 0) if row else 0
            buckets.append(
                HistoryBucket(
                    timestamp=hour_dt.isoformat(),
                    label=hour_dt.strftime("%H:%M"),
                    tool_calls=total,
                    cache_hits=hits,
                    cache_hit_rate=round(hits / total, 3) if total > 0 else 0.0,
                    errors=errors,
                )
            )

    return StatsHistoryResponse(period=period, buckets=buckets)


# ── Cost stats endpoint ───────────────────────────────────────────────────────


@router.get(
    "/cost",
    response_model=CostStatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get monthly cost breakdown (Pro+)",
)
async def get_cost_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CostStatsResponse:
    """
    Return monthly cost totals broken down by agent and MCP server.

    Cost is recorded per tool call when the MCP server has cost_per_call_usd set.
    Cache hits are free; cost_saved_by_cache reflects what would have been spent
    if those calls had hit the upstream server.

    Requires Pro or Enterprise plan.
    """
    org = await db.get(Organization, current_user.org_id)
    if not org or org.plan_tier not in PAID_TIERS:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Cost tracking requires a Pro or Enterprise plan",
        )

    month_start = func.date_trunc("month", func.now())

    # ── Total cost this month ─────────────────────────────────────────────────
    cost_result = await db.execute(
        select(func.coalesce(func.sum(SessionEvent.cost_usd), 0).label("total")).where(
            SessionEvent.org_id == current_user.org_id,
            SessionEvent.occurred_at >= month_start,
            SessionEvent.cost_usd.isnot(None),
        )
    )
    cost_this_month: float = float(cost_result.scalar_one() or 0)

    # ── Cost saved by cache: sum of cost_per_call_usd for cache hits this month ─
    cache_savings_result = await db.execute(
        select(func.coalesce(func.sum(MCPServer.cost_per_call_usd), 0).label("saved"))
        .join(MCPServer, SessionEvent.mcp_server_id == MCPServer.id)
        .where(
            SessionEvent.org_id == current_user.org_id,
            SessionEvent.occurred_at >= month_start,
            SessionEvent.cache_hit.is_(True),
            MCPServer.cost_per_call_usd.isnot(None),
        )
    )
    cost_saved: float = float(cache_savings_result.scalar_one() or 0)

    # ── Breakdown by agent ────────────────────────────────────────────────────
    by_agent_result = await db.execute(
        select(
            Agent.name.label("agent_name"),
            func.coalesce(func.sum(SessionEvent.cost_usd), 0).label("total"),
        )
        .join(Session, SessionEvent.session_id == Session.id)
        .join(Agent, Session.agent_id == Agent.id)
        .where(
            SessionEvent.org_id == current_user.org_id,
            SessionEvent.occurred_at >= month_start,
            SessionEvent.cost_usd.isnot(None),
        )
        .group_by(Agent.name)
        .order_by(func.sum(SessionEvent.cost_usd).desc())
    )
    by_agent = [
        CostBreakdownItem(name=r.agent_name, cost_usd=round(float(r.total), 6))
        for r in by_agent_result.all()
    ]

    # ── Breakdown by server ───────────────────────────────────────────────────
    by_server_result = await db.execute(
        select(
            MCPServer.name.label("server_name"),
            func.coalesce(func.sum(SessionEvent.cost_usd), 0).label("total"),
        )
        .join(MCPServer, SessionEvent.mcp_server_id == MCPServer.id)
        .where(
            SessionEvent.org_id == current_user.org_id,
            SessionEvent.occurred_at >= month_start,
            SessionEvent.cost_usd.isnot(None),
        )
        .group_by(MCPServer.name)
        .order_by(func.sum(SessionEvent.cost_usd).desc())
    )
    by_server = [
        CostBreakdownItem(name=r.server_name, cost_usd=round(float(r.total), 6))
        for r in by_server_result.all()
    ]

    return CostStatsResponse(
        cost_this_month_usd=round(cost_this_month, 6),
        cost_saved_by_cache_usd=round(cost_saved, 6),
        by_agent=by_agent,
        by_server=by_server,
    )
