"""
Arbiter — API endpoints: Stats.

Dashboard statistics endpoint returning aggregated counts and metrics.

Routes:
    GET    /stats              — return agents_count, servers_count, tool_calls_today,
                                 cache_hit_rate_today
    GET    /stats/usage/summary — monthly tool call usage + plan limit
    GET    /stats/history      — historical time-series bucketed by hour (24h) or day (7d)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query, status
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
from app.services.plan.plan_limits import PLAN_LIMITS

router = APIRouter(prefix="/stats", tags=["stats"])


# ── Schema ────────────────────────────────────────────────────────────────────


class StatsResponse(BaseModel):
    """Dashboard statistics snapshot."""

    agents_count: int
    servers_count: int
    tool_calls_today: int
    cache_hit_rate_today: float  # 0.0–1.0
    error_rate_today: float  # 0.0–1.0


class HistoryBucket(BaseModel):
    """A single time bucket of aggregated activity metrics."""

    timestamp: str        # ISO format — hour start for 24h, day start for 7d
    label: str            # "14:00" for 24h, "Mon" / "Tue" etc. for 7d
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


# ── Endpoint ──────────────────────────────────────────────────────────────────


@router.get(
    "",
    response_model=StatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get dashboard statistics",
)
async def get_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
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
    agents_result = await db.execute(
        select(func.count(Agent.id)).where(Agent.is_active.is_(True), Agent.org_id == current_user.org_id)
    )
    agents_count: int = agents_result.scalar_one() or 0

    # ── Active MCP servers count ───────────────────────────────────────────────
    servers_result = await db.execute(
        select(func.count(MCPServer.id)).where(MCPServer.is_active.is_(True), MCPServer.org_id == current_user.org_id)
    )
    servers_count: int = servers_result.scalar_one() or 0

    # ── Today's tool calls and cache hit rate ──────────────────────────────────
    today_midnight = func.date_trunc("day", func.now())

    org_session_ids_today = select(Session.id).where(Session.org_id == current_user.org_id).scalar_subquery()
    calls_result = await db.execute(
        select(
            func.count(SessionEvent.id).label("total"),
            func.sum(case((SessionEvent.cache_hit.is_(True), 1), else_=0)).label("hits"),
            func.sum(case((SessionEvent.error.isnot(None), 1), else_=0)).label("errors"),
        ).where(
            SessionEvent.occurred_at >= today_midnight,
            SessionEvent.org_id == current_user.org_id,
            SessionEvent.session_id.in_(org_session_ids_today),
        )
    )
    row = calls_result.one()
    tool_calls_today: int = row.total or 0
    hits_today: int = row.hits or 0
    errors_today: int = row.errors or 0

    cache_hit_rate_today: float = hits_today / tool_calls_today if tool_calls_today > 0 else 0.0
    error_rate_today: float = errors_today / tool_calls_today if tool_calls_today > 0 else 0.0

    return StatsResponse(
        agents_count=agents_count,
        servers_count=servers_count,
        tool_calls_today=tool_calls_today,
        cache_hit_rate_today=cache_hit_rate_today,
        error_rate_today=error_rate_today,
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
    period: str = Query("7d", description="Time period: '7d' (daily buckets) or '24h' (hourly buckets)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StatsHistoryResponse:
    """
    Return historical time-series activity data for the dashboard chart.

    For period='7d': 7 daily buckets (one per day, oldest first).
    For period='24h': 24 hourly buckets (one per hour, oldest first).
    Buckets with no events are filled with zeros.

    Args:
        period:   '7d' or '24h'.
        db:       Injected DB session.
        _current: Auth guard — valid API key required.

    Returns:
        StatsHistoryResponse: period + list of HistoryBucket.

    Raises:
        422: If period is not '7d' or '24h'.
    """
    from fastapi import HTTPException

    if period not in ("7d", "24h"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="period must be '7d' or '24h'",
        )

    now = datetime.now(timezone.utc)

    if period == "7d":
        cutoff = now - timedelta(days=7)
        org_session_ids = select(Session.id).where(Session.org_id == current_user.org_id).scalar_subquery()
        day_bucket = literal_column("date_trunc('day', session_events.occurred_at)")
        result = await db.execute(
            select(
                day_bucket.label("bucket"),
                func.count().label("total"),
                func.sum(case((SessionEvent.cache_hit.is_(True), 1), else_=0)).label("hits"),
                func.sum(case((SessionEvent.error.isnot(None), 1), else_=0)).label("errors"),
            )
            .where(
                SessionEvent.occurred_at >= cutoff,
                SessionEvent.org_id == current_user.org_id,
                SessionEvent.session_id.in_(org_session_ids),
            )
            .group_by(day_bucket)
            .order_by(day_bucket)
        )
        rows = result.all()

        # Key by date string
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
            bucket_dt = datetime.combine(day, datetime.min.time()).replace(tzinfo=timezone.utc)
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
        org_session_ids = select(Session.id).where(Session.org_id == current_user.org_id).scalar_subquery()
        hour_bucket = literal_column("date_trunc('hour', session_events.occurred_at)")
        result = await db.execute(
            select(
                hour_bucket.label("bucket"),
                func.count().label("total"),
                func.sum(case((SessionEvent.cache_hit.is_(True), 1), else_=0)).label("hits"),
                func.sum(case((SessionEvent.error.isnot(None), 1), else_=0)).label("errors"),
            )
            .where(
                SessionEvent.occurred_at >= cutoff,
                SessionEvent.org_id == current_user.org_id,
                SessionEvent.session_id.in_(org_session_ids),
            )
            .group_by(hour_bucket)
            .order_by(hour_bucket)
        )
        rows = result.all()

        # Key by ISO hour string (e.g. "2024-03-25T14:00:00+00:00")
        data_by_key = {}
        for row in rows:
            hour_dt = row.bucket.replace(minute=0, second=0, microsecond=0)
            if hour_dt.tzinfo is None:
                hour_dt = hour_dt.replace(tzinfo=timezone.utc)
            hour_key = hour_dt.strftime("%Y-%m-%dT%H")
            data_by_key[hour_key] = row

        buckets = []
        # Start from the hour that was 23 hours ago, up to the current hour
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
