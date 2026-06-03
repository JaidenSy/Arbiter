"""
Arbiter — API endpoints: Analytics.

Per-agent cost attribution with 7-day daily trend data.

Routes:
    GET    /analytics/agents — monthly tool-call breakdown by agent (Pro+ only)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.db.models.agent import Agent
from app.db.models.organization import Organization
from app.db.models.session import Session, SessionEvent
from app.db.models.user import User
from app.schemas.analytics import AgentAnalyticsResponse, AgentTrendPoint, AgentUsage
from app.services.plan.plan_limits import PLAN_LIMITS

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get(
    "/agents",
    response_model=AgentAnalyticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get per-agent cost attribution",
)
async def get_agent_analytics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AgentAnalyticsResponse:
    """
    Return monthly tool-call counts broken down by agent, plus a 7-day daily
    trend for each agent.  Sorted by tool_calls_this_month DESC.

    Requires Pro or Enterprise plan — free orgs receive HTTP 402.
    """
    org = await db.get(Organization, current_user.org_id)
    plan_tier = org.plan_tier if org else "free"

    if plan_tier == "free":
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Upgrade to Pro to access analytics",
        )

    org_quota: int | None = PLAN_LIMITS.get(plan_tier, {}).get("max_tool_calls_mo")
    now = datetime.now(timezone.utc)
    month_start = func.date_trunc("month", func.now())
    trend_cutoff = now - timedelta(days=7)

    # ── Monthly totals per agent (single JOIN query, no N+1) ──────────────────
    monthly_q = (
        select(
            Session.agent_id,
            Agent.name.label("agent_name"),
            func.count().label("tool_calls"),
        )
        .select_from(SessionEvent)
        .join(Session, SessionEvent.session_id == Session.id)
        .join(Agent, Session.agent_id == Agent.id)
        .where(
            SessionEvent.org_id == current_user.org_id,
            SessionEvent.occurred_at >= month_start,
        )
        .group_by(Session.agent_id, Agent.name)
        .order_by(func.count().desc())
    )
    monthly_rows = (await db.execute(monthly_q)).all()

    # ── 7-day daily trend per agent (single JOIN query, no N+1) ──────────────
    day_col = func.date(SessionEvent.occurred_at).label("day")
    trend_q = (
        select(
            Session.agent_id,
            day_col,
            func.count().label("tool_calls"),
        )
        .select_from(SessionEvent)
        .join(Session, SessionEvent.session_id == Session.id)
        .where(
            SessionEvent.org_id == current_user.org_id,
            SessionEvent.occurred_at >= trend_cutoff,
        )
        .group_by(Session.agent_id, day_col)
    )
    trend_rows = (await db.execute(trend_q)).all()

    # Index trend data: {agent_id: {date_iso: count}}
    trend_by_agent: dict[object, dict[str, int]] = {}
    for row in trend_rows:
        aid = row.agent_id
        day_str = row.day.isoformat() if hasattr(row.day, "isoformat") else str(row.day)
        trend_by_agent.setdefault(aid, {})[day_str] = int(row.tool_calls)

    # Seven calendar dates: [day-6, day-5, ..., today] oldest → newest
    last_7_days = [(now - timedelta(days=i)).date() for i in range(6, -1, -1)]

    org_total = sum(int(r.tool_calls) for r in monthly_rows)

    agents: list[AgentUsage] = []
    for row in monthly_rows:
        monthly_count = int(row.tool_calls)
        pct = round(monthly_count / org_quota, 4) if org_quota else 0.0
        agent_trend_data = trend_by_agent.get(row.agent_id, {})
        trend = [
            AgentTrendPoint(
                date=d.isoformat(),
                tool_calls=agent_trend_data.get(d.isoformat(), 0),
            )
            for d in last_7_days
        ]
        agents.append(
            AgentUsage(
                agent_id=row.agent_id,
                agent_name=row.agent_name,
                tool_calls_this_month=monthly_count,
                pct_of_org_quota=pct,
                trend=trend,
            )
        )

    return AgentAnalyticsResponse(
        period=now.strftime("%Y-%m"),
        agents=agents,
        org_total_this_month=org_total,
        org_quota=org_quota,
    )
