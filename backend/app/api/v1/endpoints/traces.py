"""
Arbiter API endpoints: Execution Traces.

A "trace" is a Session with its SessionEvents shaped for waterfall timeline
rendering.  No new schema is needed: Sessions ARE traces.

Routes:
    GET    /traces               : paginated trace list (Pro+ only)
    GET    /traces/{trace_id}    : trace detail with ordered steps (Pro+ only)
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import get_current_user, get_db
from app.db.models.mcp_server import MCPServer
from app.db.models.organization import Organization
from app.db.models.session import Session
from app.db.models.user import User
from app.schemas.trace import TraceDetailResponse, TraceListItem, TraceListResponse, TraceStep
from app.services.plan.plan_limits import PAID_TIERS

router = APIRouter(prefix="/traces", tags=["traces"])


def _compute_status(ended_at, error_count: int) -> str:
    if ended_at is None:
        return "active"
    if error_count > 0:
        return "failed"
    return "completed"


def _duration_ms(started_at, ended_at) -> int | None:
    if ended_at is None or started_at is None:
        return None
    delta = ended_at - started_at
    return int(delta.total_seconds() * 1000)


async def _require_pro(org_id: uuid.UUID, db: AsyncSession) -> None:
    org = await db.get(Organization, org_id)
    plan_tier = org.plan_tier if org else "free"
    if plan_tier not in PAID_TIERS:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Upgrade to Pro to access execution traces",
        )


@router.get(
    "",
    response_model=TraceListResponse,
    status_code=status.HTTP_200_OK,
    summary="List execution traces",
)
async def list_traces(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=200, description="Items per page"),
    agent_id: uuid.UUID | None = Query(None, description="Filter by agent UUID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TraceListResponse:
    """
    Return a paginated list of execution traces (sessions) for the org.

    Each item includes aggregated tool_call_count, error_count, and a derived
    status.  Requires Pro or Enterprise plan.
    """
    await _require_pro(current_user.org_id, db)

    conditions = [Session.org_id == current_user.org_id]
    if agent_id is not None:
        conditions.append(Session.agent_id == agent_id)

    total = await db.scalar(select(func.count(Session.id)).where(*conditions)) or 0

    offset = (page - 1) * page_size
    result = await db.execute(
        select(Session)
        .where(*conditions)
        .order_by(Session.started_at.desc())
        .offset(offset)
        .limit(page_size)
        .options(selectinload(Session.agent), selectinload(Session.events))
    )
    sessions = result.scalars().all()

    traces: list[TraceListItem] = []
    for s in sessions:
        error_count = sum(1 for e in s.events if e.error is not None)
        traces.append(
            TraceListItem(
                trace_id=s.id,
                agent_id=s.agent_id,
                agent_name=s.agent.name if s.agent else "unknown",
                started_at=s.started_at,
                ended_at=s.ended_at,
                duration_ms=_duration_ms(s.started_at, s.ended_at),
                tool_call_count=len(s.events),
                error_count=error_count,
                status=_compute_status(s.ended_at, error_count),
            )
        )

    return TraceListResponse(traces=traces, total=total, page=page, page_size=page_size)


@router.get(
    "/{trace_id}",
    response_model=TraceDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get trace detail with waterfall steps",
)
async def get_trace(
    trace_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TraceDetailResponse:
    """
    Return a single trace with its ordered steps for waterfall timeline rendering.

    offset_ms on each step is the milliseconds elapsed from trace start: lets
    the frontend position bars on a shared time axis.

    Requires Pro or Enterprise plan.  Returns 404 if the trace belongs to a
    different org (never leak cross-org data).
    """
    await _require_pro(current_user.org_id, db)

    result = await db.execute(
        select(Session)
        .where(Session.id == trace_id, Session.org_id == current_user.org_id)
        .options(
            selectinload(Session.agent),
            selectinload(Session.events),
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trace {trace_id} not found",
        )

    # Build MCP server name lookup in a single query.
    server_ids = {e.mcp_server_id for e in session.events if e.mcp_server_id}
    server_map: dict[uuid.UUID, str] = {}
    if server_ids:
        sr = await db.execute(
            select(MCPServer.id, MCPServer.name).where(
                MCPServer.id.in_(server_ids),
                MCPServer.org_id == current_user.org_id,
            )
        )
        server_map = {row.id: row.name for row in sr}

    # Events are already ordered by occurred_at via the relationship definition.
    steps: list[TraceStep] = []
    for idx, event in enumerate(session.events, start=1):
        if session.started_at is not None and event.occurred_at is not None:
            offset_ms = (event.occurred_at - session.started_at).total_seconds() * 1000
        else:
            offset_ms = 0.0
        steps.append(
            TraceStep(
                step=idx,
                tool_name=event.tool_name,
                mcp_server_name=server_map.get(event.mcp_server_id)
                if event.mcp_server_id
                else None,
                occurred_at=event.occurred_at,
                duration_ms=event.duration_ms,
                cache_hit=event.cache_hit,
                status="error" if event.error is not None else "ok",
                error=event.error,
                offset_ms=offset_ms,
            )
        )

    error_count = sum(1 for e in session.events if e.error is not None)
    return TraceDetailResponse(
        trace_id=session.id,
        agent_id=session.agent_id,
        agent_name=session.agent.name if session.agent else "unknown",
        started_at=session.started_at,
        ended_at=session.ended_at,
        duration_ms=_duration_ms(session.started_at, session.ended_at),
        status=_compute_status(session.ended_at, error_count),
        steps=steps,
    )
