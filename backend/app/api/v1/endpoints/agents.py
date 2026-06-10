"""
Arbiter — API endpoints: Agents.

Manages agent registration and lifecycle.  API keys are generated on
creation and returned ONCE; the hash is stored, never the raw key.

Routes:
    POST   /agents               — register a new agent, returns raw API key once
    GET    /agents               — list all active agents (paginated)
    GET    /agents/{id}          — get a single agent by UUID
    DELETE /agents/{id}          — soft-delete (sets is_active=False); does not count against plan cap
    POST   /agents/{id}/rotate-key — invalidate old key, issue new one (returned once)
    GET    /agents/{id}/risk     — anomaly risk score (Pro+ only)
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.dependencies import get_current_user, get_db, get_redis, require_role
from app.db.models.agent import Agent
from app.db.models.organization import Organization
from app.db.models.user import User
from app.schemas.agent import (
    _VALID_SCOPES,
    AgentCreate,
    AgentCreateResponse,
    AgentResponse,
    AgentUpdate,
)
from app.schemas.pagination import Page
from app.schemas.proxy import ToolCallRequest, ToolCallResponse
from app.schemas.risk import AgentRiskResponse, AgentRiskSignals
from app.services.plan.plan_service import check_resource_limit
from app.services.proxy.proxy_service import ProxyService

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post(
    "",
    response_model=AgentCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new agent",
)
async def create_agent(
    body: AgentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner", "admin")),
) -> AgentCreateResponse:
    if body.scope not in _VALID_SCOPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid scope {body.scope!r}. Must be one of: {sorted(_VALID_SCOPES)}",
        )

    existing = await db.execute(
        select(Agent).where(
            Agent.name == body.name,
            Agent.org_id == current_user.org_id,
            Agent.is_active.is_(True),
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An agent named {body.name!r} already exists",
        )

    org = await db.get(Organization, current_user.org_id)
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Org not found",
        )
    await check_resource_limit(
        db=db,
        org=org,
        resource="agents",
        model=Agent,
        filter_col=Agent.org_id,
        count_active_only=True,
    )

    raw_key = security.generate_api_key()
    key_hash = security.hash_api_key(raw_key)

    agent = Agent(
        org_id=current_user.org_id,
        name=body.name,
        description=body.description,
        api_key_hash=key_hash,
        is_active=True,
        scope=body.scope,
        rate_limit_per_minute=body.rate_limit_per_minute,
        max_calls_per_session=body.max_calls_per_session,
        created_by_user_id=current_user.id,
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)

    return AgentCreateResponse(
        id=agent.id,
        name=agent.name,
        description=agent.description,
        is_active=agent.is_active,
        scope=agent.scope,
        rate_limit_per_minute=agent.rate_limit_per_minute,
        max_calls_per_session=agent.max_calls_per_session,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
        api_key=raw_key,
    )


@router.get(
    "",
    response_model=Page[AgentResponse],
    summary="List all agents",
)
async def list_agents(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Page[AgentResponse]:
    limit = min(limit, 200)
    where = (Agent.is_active.is_(True), Agent.org_id == current_user.org_id)
    total: int = await db.scalar(select(func.count(Agent.id)).where(*where)) or 0
    result = await db.execute(
        select(Agent).where(*where).order_by(Agent.created_at.desc()).offset(skip).limit(limit)
    )
    return Page(
        items=[AgentResponse.model_validate(a) for a in result.scalars().all()],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{agent_id}",
    response_model=AgentResponse,
    summary="Get agent by ID",
)
async def get_agent(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AgentResponse:
    result = await db.execute(
        select(Agent).where(
            Agent.id == agent_id,
            Agent.is_active.is_(True),
            Agent.org_id == current_user.org_id,
        )
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agent_id} not found",
        )
    return AgentResponse.model_validate(agent)


@router.patch(
    "/{agent_id}",
    response_model=AgentResponse,
    summary="Update agent name or description",
)
async def update_agent(
    agent_id: uuid.UUID,
    body: AgentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner", "admin")),
) -> AgentResponse:
    result = await db.execute(
        select(Agent).where(
            Agent.id == agent_id,
            Agent.is_active.is_(True),
            Agent.org_id == current_user.org_id,
        )
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent {agent_id} not found"
        )

    if body.name is not None:
        existing = await db.execute(
            select(Agent).where(
                Agent.name == body.name,
                Agent.org_id == current_user.org_id,
                Agent.id != agent_id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"An agent named {body.name!r} already exists",
            )
        agent.name = body.name
    if body.description is not None:
        agent.description = body.description
    if "rate_limit_per_minute" in body.model_fields_set:
        agent.rate_limit_per_minute = body.rate_limit_per_minute
    if "max_calls_per_session" in body.model_fields_set:
        agent.max_calls_per_session = body.max_calls_per_session

    await db.commit()
    await db.refresh(agent)
    return AgentResponse.model_validate(agent)


@router.delete(
    "/{agent_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate an agent",
)
async def delete_agent(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner", "admin")),
) -> Response:
    result = await db.execute(
        select(Agent).where(
            Agent.id == agent_id,
            Agent.org_id == current_user.org_id,
        )
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agent_id} not found",
        )
    agent.is_active = False
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{agent_id}/rotate-key",
    response_model=AgentCreateResponse,
    status_code=status.HTTP_200_OK,
    summary="Rotate API key — old key is immediately invalidated",
)
async def rotate_api_key(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner", "admin")),
) -> AgentCreateResponse:
    result = await db.execute(
        select(Agent).where(
            Agent.id == agent_id,
            Agent.is_active.is_(True),
            Agent.org_id == current_user.org_id,
        )
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agent_id} not found",
        )

    raw_key = security.generate_api_key()
    agent.api_key_hash = security.hash_api_key(raw_key)
    await db.commit()
    await db.refresh(agent)

    return AgentCreateResponse(
        id=agent.id,
        name=agent.name,
        description=agent.description,
        is_active=agent.is_active,
        scope=agent.scope,
        rate_limit_per_minute=agent.rate_limit_per_minute,
        max_calls_per_session=agent.max_calls_per_session,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
        api_key=raw_key,
    )


@router.post(
    "/{agent_id}/test-call",
    response_model=ToolCallResponse,
    summary="Test a proxy tool call using this agent's identity",
)
async def test_tool_call(
    agent_id: uuid.UUID,
    body: ToolCallRequest,
    db: AsyncSession = Depends(get_db),
    redis: object = Depends(get_redis),
    current_user: User = Depends(require_role("owner", "admin")),
) -> ToolCallResponse:
    """Fire a real proxy tool call on behalf of an agent using user JWT auth."""
    result = await db.execute(
        select(Agent).where(
            Agent.id == agent_id,
            Agent.org_id == current_user.org_id,
            Agent.is_active.is_(True),
        )
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent {agent_id} not found"
        )

    service = ProxyService(db=db, redis=redis)
    return await service.forward_tool_call(request=body, agent=agent)


# ── Risk / anomaly detection helpers ─────────────────────────────────────────

_HOURS_IN_7_DAYS = 168
_RISK_CACHE_TTL = 60  # seconds — risk scores are recomputed at most once per minute

_RISK_WEIGHTS = {
    "error_rate_spike": 0.35,
    "burst_ratio": 0.25,
    "novel_tool_count": 0.20,
    "latency_spike_ratio": 0.10,
    "off_hours_ratio_24h": 0.10,
}

_MAIN_STATS_SQL = text("""
    SELECT
        COUNT(*) FILTER (WHERE se.occurred_at >= NOW() - INTERVAL '7 days')  AS total_7d,
        COUNT(*) FILTER (WHERE se.occurred_at >= NOW() - INTERVAL '24 hours') AS total_24h,
        COUNT(*) FILTER (WHERE se.occurred_at >= NOW() - INTERVAL '1 hour')   AS total_1h,
        COUNT(*) FILTER (
            WHERE se.occurred_at >= NOW() - INTERVAL '7 days'
              AND se.error IS NOT NULL
        ) AS errors_7d,
        COUNT(*) FILTER (
            WHERE se.occurred_at >= NOW() - INTERVAL '24 hours'
              AND se.error IS NOT NULL
        ) AS errors_24h,
        AVG(se.duration_ms) FILTER (
            WHERE se.occurred_at >= NOW() - INTERVAL '7 days'
              AND se.duration_ms IS NOT NULL
        ) AS avg_dur_7d,
        AVG(se.duration_ms) FILTER (
            WHERE se.occurred_at >= NOW() - INTERVAL '24 hours'
              AND se.duration_ms IS NOT NULL
        ) AS avg_dur_24h,
        COUNT(*) FILTER (
            WHERE se.occurred_at >= NOW() - INTERVAL '24 hours'
              AND (
                  EXTRACT(HOUR FROM se.occurred_at AT TIME ZONE 'UTC') < 6
                  OR EXTRACT(HOUR FROM se.occurred_at AT TIME ZONE 'UTC') >= 22
              )
        ) AS off_hours_24h
    FROM session_events se
    JOIN sessions s ON s.id = se.session_id
    WHERE s.agent_id = :agent_id
      AND s.org_id   = :org_id
      AND se.occurred_at >= NOW() - INTERVAL '7 days'
""")

_NOVEL_TOOLS_SQL = text("""
    WITH prior_tools AS (
        SELECT DISTINCT se.tool_name
        FROM session_events se
        JOIN sessions s ON s.id = se.session_id
        WHERE s.agent_id = :agent_id
          AND s.org_id   = :org_id
          AND se.occurred_at >= NOW() - INTERVAL '7 days'
          AND se.occurred_at <  NOW() - INTERVAL '24 hours'
    ),
    recent_tools AS (
        SELECT DISTINCT se.tool_name
        FROM session_events se
        JOIN sessions s ON s.id = se.session_id
        WHERE s.agent_id = :agent_id
          AND s.org_id   = :org_id
          AND se.occurred_at >= NOW() - INTERVAL '24 hours'
    )
    SELECT COUNT(*) AS novel_tool_count
    FROM recent_tools rt
    WHERE rt.tool_name NOT IN (SELECT tool_name FROM prior_tools)
""")


def _score_to_level(score: float) -> str:
    if score < 0.25:
        return "low"
    if score < 0.50:
        return "medium"
    if score < 0.75:
        return "high"
    return "critical"


def _build_signals(
    total_7d: int,
    total_24h: int,
    total_1h: int,
    errors_7d: int,
    errors_24h: int,
    avg_dur_7d: float | None,
    avg_dur_24h: float | None,
    off_hours_24h: int,
    novel_count: int,
) -> AgentRiskSignals:
    # ── Signal 1: error_rate_spike ────────────────────────────────────────────
    total_baseline = total_7d - total_24h
    errors_baseline = errors_7d - errors_24h
    rate_24h = errors_24h / total_24h if total_24h > 0 else 0.0
    rate_baseline = errors_baseline / total_baseline if total_baseline > 0 else 0.0
    if total_24h > 0 and rate_24h > 2.0 * rate_baseline:
        error_spike = 1.0
    else:
        error_spike = 0.0

    # ── Signal 2: burst_ratio ─────────────────────────────────────────────────
    hourly_avg = total_7d / _HOURS_IN_7_DAYS
    raw_burst = total_1h / max(hourly_avg, 0.001)
    burst = min(raw_burst / 10.0, 1.0)

    # ── Signal 3: novel_tool_count ────────────────────────────────────────────
    novel = min(novel_count / 5.0, 1.0)

    # ── Signal 4: latency_spike_ratio ─────────────────────────────────────────
    if avg_dur_7d and avg_dur_7d > 0 and avg_dur_24h and avg_dur_24h > 2.0 * avg_dur_7d:
        latency_spike = 1.0
    else:
        latency_spike = 0.0

    # ── Signal 5: off_hours_ratio_24h ─────────────────────────────────────────
    off_hours = off_hours_24h / max(total_24h, 1)

    return AgentRiskSignals(
        error_rate_spike=round(error_spike, 4),
        burst_ratio=round(burst, 4),
        novel_tool_count=round(novel, 4),
        latency_spike_ratio=round(latency_spike, 4),
        off_hours_ratio_24h=round(off_hours, 4),
    )


# ── Risk endpoint ─────────────────────────────────────────────────────────────


@router.get(
    "/{agent_id}/risk",
    response_model=AgentRiskResponse,
    summary="Anomaly risk score for an agent (Pro+ only)",
)
async def get_agent_risk(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    redis: object = Depends(get_redis),
    current_user: User = Depends(get_current_user),
) -> AgentRiskResponse:
    org = await db.get(Organization, current_user.org_id)
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Org not found"
        )

    if org.plan_tier not in ("pro", "enterprise"):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Anomaly detection requires a Pro or Enterprise plan",
        )

    cache_key = f"agent_risk:{current_user.org_id}:{agent_id}"
    cached = await redis.get(cache_key)
    if cached is not None:
        return AgentRiskResponse.model_validate_json(cached)

    result = await db.execute(
        select(Agent).where(
            Agent.id == agent_id,
            Agent.is_active.is_(True),
            Agent.org_id == current_user.org_id,
        )
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agent_id} not found",
        )

    params = {"agent_id": str(agent_id), "org_id": str(current_user.org_id)}

    stats_row = (await db.execute(_MAIN_STATS_SQL, params)).mappings().one()
    novel_row = (await db.execute(_NOVEL_TOOLS_SQL, params)).mappings().one()

    signals = _build_signals(
        total_7d=int(stats_row["total_7d"] or 0),
        total_24h=int(stats_row["total_24h"] or 0),
        total_1h=int(stats_row["total_1h"] or 0),
        errors_7d=int(stats_row["errors_7d"] or 0),
        errors_24h=int(stats_row["errors_24h"] or 0),
        avg_dur_7d=float(stats_row["avg_dur_7d"]) if stats_row["avg_dur_7d"] is not None else None,
        avg_dur_24h=float(stats_row["avg_dur_24h"])
        if stats_row["avg_dur_24h"] is not None
        else None,
        off_hours_24h=int(stats_row["off_hours_24h"] or 0),
        novel_count=int(novel_row["novel_tool_count"] or 0),
    )

    score = round(
        signals.error_rate_spike * _RISK_WEIGHTS["error_rate_spike"]
        + signals.burst_ratio * _RISK_WEIGHTS["burst_ratio"]
        + signals.novel_tool_count * _RISK_WEIGHTS["novel_tool_count"]
        + signals.latency_spike_ratio * _RISK_WEIGHTS["latency_spike_ratio"]
        + signals.off_hours_ratio_24h * _RISK_WEIGHTS["off_hours_ratio_24h"],
        4,
    )

    response = AgentRiskResponse(
        agent_id=agent_id,
        score=score,
        level=_score_to_level(score),
        signals=signals,
    )
    await redis.setex(cache_key, _RISK_CACHE_TTL, response.model_dump_json())
    return response
