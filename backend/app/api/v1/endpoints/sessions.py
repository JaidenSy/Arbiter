"""
Arbiter — API endpoints: Sessions.

Sessions are created automatically by the proxy when a tool call is
received without a session_id.  These endpoints expose read-only access
to session history and per-session event logs for auditing.

Routes:
    GET    /sessions              — list sessions (filterable by agent_id)
    GET    /sessions/{id}         — get session with all events
    GET    /sessions/{id}/events  — get events for a session (paginated)
"""

from __future__ import annotations

import csv
import io
import json
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import get_current_user, get_db
from app.db.models.mcp_server import MCPServer
from app.db.models.session import Session, SessionEvent
from app.db.models.user import User
from app.schemas.pagination import Page
from app.schemas.session import (
    ChainNode,
    SessionEventResponse,
    SessionListResponse,
    SessionResponse,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get(
    "",
    response_model=Page[SessionListResponse],
    summary="List sessions",
)
async def list_sessions(
    agent_id: uuid.UUID | None = Query(None, description="Filter by agent UUID"),
    tool_name: str | None = Query(None, description="Filter sessions that called this tool"),
    has_error: bool | None = Query(None, description="True = only sessions with errors"),
    from_date: datetime | None = Query(
        None, description="Sessions started on or after this ISO timestamp"
    ),
    to_date: datetime | None = Query(
        None, description="Sessions started on or before this ISO timestamp"
    ),
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Page[SessionListResponse]:
    limit = min(limit, 200)
    if from_date is not None and to_date is not None and from_date > to_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="from_date must be before to_date",
        )
    conditions = [Session.org_id == current_user.org_id]
    if agent_id is not None:
        conditions.append(Session.agent_id == agent_id)
    if from_date is not None:
        conditions.append(Session.started_at >= from_date)
    if to_date is not None:
        conditions.append(Session.started_at <= to_date)
    if tool_name is not None:
        conditions.append(
            exists(
                select(SessionEvent.id).where(
                    SessionEvent.session_id == Session.id,
                    SessionEvent.tool_name == tool_name,
                )
            )
        )
    if has_error is True:
        conditions.append(
            exists(
                select(SessionEvent.id).where(
                    SessionEvent.session_id == Session.id,
                    SessionEvent.error.isnot(None),
                )
            )
        )
    elif has_error is False:
        conditions.append(
            ~exists(
                select(SessionEvent.id).where(
                    SessionEvent.session_id == Session.id,
                    SessionEvent.error.isnot(None),
                )
            )
        )

    total = await db.scalar(select(func.count(Session.id)).where(*conditions)) or 0
    result = await db.execute(
        select(
            Session.id,
            Session.agent_id,
            Session.parent_session_id,
            Session.trace_id,
            Session.started_at,
            Session.ended_at,
            Session.metadata_,
            func.count(SessionEvent.id).label("event_count"),
            func.bool_or(SessionEvent.error.isnot(None)).label("has_error"),
        )
        .outerjoin(SessionEvent, SessionEvent.session_id == Session.id)
        .where(*conditions)
        .group_by(
            Session.id,
            Session.agent_id,
            Session.parent_session_id,
            Session.trace_id,
            Session.started_at,
            Session.ended_at,
            Session.metadata_,
        )
        .order_by(Session.started_at.desc())
        .offset(skip)
        .limit(limit)
    )
    rows = result.all()
    return Page(
        items=[
            SessionListResponse(
                id=row.id,
                agent_id=row.agent_id,
                parent_session_id=row.parent_session_id,
                trace_id=row.trace_id,
                started_at=row.started_at,
                ended_at=row.ended_at,
                metadata_=row.metadata_ or {},
                event_count=row.event_count,
                has_error=bool(row.has_error),
            )
            for row in rows
        ],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/export",
    summary="Export session events as CSV or JSON",
    response_class=StreamingResponse,
)
async def export_sessions(
    format: str = Query("csv", description="Export format: 'csv' or 'json'"),
    from_date: datetime | None = Query(None, description="Start of date range (ISO timestamp)"),
    to_date: datetime | None = Query(None, description="End of date range (ISO timestamp)"),
    agent_id: uuid.UUID | None = Query(None, description="Filter by agent UUID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Stream session events for the org as CSV or JSON for compliance/audit export."""
    if format not in ("csv", "json"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="format must be 'csv' or 'json'",
        )
    if from_date is not None and to_date is not None and from_date > to_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="from_date must be before to_date",
        )

    session_query = select(Session).where(Session.org_id == current_user.org_id)
    if agent_id is not None:
        session_query = session_query.where(Session.agent_id == agent_id)
    if from_date is not None:
        session_query = session_query.where(Session.started_at >= from_date)
    if to_date is not None:
        session_query = session_query.where(Session.started_at <= to_date)

    session_result = await db.execute(session_query.options(selectinload(Session.events)))
    sessions = session_result.scalars().all()

    all_server_ids = {e.mcp_server_id for s in sessions for e in s.events if e.mcp_server_id}
    server_map: dict[uuid.UUID, str] = {}
    if all_server_ids:
        sr = await db.execute(
            select(MCPServer.id, MCPServer.name).where(
                MCPServer.id.in_(all_server_ids),
                MCPServer.org_id == current_user.org_id,
            )
        )
        server_map = {row.id: row.name for row in sr}

    rows = []
    for s in sessions:
        for e in s.events:
            rows.append(
                {
                    "session_id": str(s.id),
                    "agent_id": str(s.agent_id),
                    "event_id": str(e.id),
                    "tool_name": e.tool_name,
                    "mcp_server": server_map.get(e.mcp_server_id, ""),
                    "cache_hit": e.cache_hit,
                    "duration_ms": e.duration_ms,
                    "error": e.error or "",
                    "occurred_at": e.occurred_at.isoformat() if e.occurred_at else "",
                }
            )

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    if format == "json":
        content = json.dumps(rows, indent=2)
        return StreamingResponse(
            iter([content]),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="arbiter_export_{ts}.json"'},
        )

    buf = io.StringIO()
    if rows:
        writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="arbiter_export_{ts}.csv"'},
    )


@router.get(
    "/{session_id}",
    response_model=SessionResponse,
    summary="Get session with events",
)
async def get_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SessionResponse:
    """
    Return a session and all of its audit events.

    Events are eagerly loaded in a single query to avoid N+1 queries.

    Args:
        session_id: UUID of the session to retrieve.
        db:         Injected DB session.
        _current:   Auth guard.

    Returns:
        SessionResponse: Full session with nested events list.

    Raises:
        HTTPException 404: If the session does not exist.
    """
    result = await db.execute(
        select(Session)
        .where(Session.id == session_id, Session.org_id == current_user.org_id)
        .options(selectinload(Session.events), selectinload(Session.children))
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    server_ids = {e.mcp_server_id for e in session.events if e.mcp_server_id}
    server_map: dict[uuid.UUID, str] = {}
    if server_ids:
        servers_result = await db.execute(
            select(MCPServer.id, MCPServer.name).where(
                MCPServer.id.in_(server_ids),
                MCPServer.org_id == current_user.org_id,
            )
        )
        server_map = {row.id: row.name for row in servers_result}

    session_data = SessionResponse.model_validate(session)
    enriched_events: list[SessionEventResponse] = []
    for event, schema_event in zip(session.events, session_data.events):
        schema_event.mcp_server_name = server_map.get(event.mcp_server_id)
        enriched_events.append(schema_event)
    session_data.events = enriched_events
    session_data.children = [SessionListResponse.model_validate(c) for c in session.children]
    return session_data


@router.get(
    "/{session_id}/events",
    response_model=Page[SessionEventResponse],
    summary="List events for a session",
)
async def list_session_events(
    session_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Page[SessionEventResponse]:
    """
    Return paginated audit events for a specific session.

    Useful for streaming large session histories without loading everything.

    Args:
        session_id: UUID of the parent session.
        skip:       Pagination offset.
        limit:      Max events to return (capped at 500).
        db:         Injected DB session.
        _current:   Auth guard.

    Returns:
        Page[SessionEventResponse]: Events ordered by occurred_at ASC.

    Raises:
        HTTPException 404: If the session does not exist.
    """
    # Verify the session exists AND belongs to the current user's org.
    session_result = await db.execute(
        select(Session).where(
            Session.id == session_id,
            Session.org_id == current_user.org_id,
        )
    )
    if session_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    limit = min(limit, 500)
    total = (
        await db.scalar(
            select(func.count(SessionEvent.id)).where(SessionEvent.session_id == session_id)
        )
        or 0
    )
    result = await db.execute(
        select(SessionEvent)
        .where(SessionEvent.session_id == session_id)
        .order_by(SessionEvent.occurred_at.asc())
        .offset(skip)
        .limit(limit)
    )
    events = result.scalars().all()

    # Enrich each event with the human-readable MCP server name.
    server_ids = {e.mcp_server_id for e in events if e.mcp_server_id}
    server_map: dict[uuid.UUID, str] = {}
    if server_ids:
        servers_result = await db.execute(
            select(MCPServer.id, MCPServer.name).where(
                MCPServer.id.in_(server_ids),
                MCPServer.org_id == current_user.org_id,
            )
        )
        server_map = {row.id: row.name for row in servers_result}

    enriched: list[SessionEventResponse] = []
    for event in events:
        schema_event = SessionEventResponse.model_validate(event)
        schema_event.mcp_server_name = server_map.get(event.mcp_server_id)
        enriched.append(schema_event)
    return Page(items=enriched, total=total, skip=skip, limit=limit)


@router.get(
    "/{session_id}/chain",
    response_model=ChainNode,
    summary="Get the full multi-hop call chain for a session",
)
async def get_session_chain(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChainNode:
    """
    Return the full call chain tree rooted at the trace_id root for this session.

    All sessions sharing the same trace_id are fetched in one query and assembled
    into a tree.  The returned root node is the session with no parent in the chain.
    """
    # Fetch the requested session to get its trace_id.
    target_result = await db.execute(
        select(Session).where(
            Session.id == session_id,
            Session.org_id == current_user.org_id,
        )
    )
    target = target_result.scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    # Fetch all sessions sharing the same trace_id (whole chain, one query).
    chain_result = await db.execute(
        select(
            Session.id,
            Session.agent_id,
            Session.parent_session_id,
            Session.trace_id,
            Session.started_at,
            Session.ended_at,
            func.count(SessionEvent.id).label("event_count"),
        )
        .outerjoin(SessionEvent, SessionEvent.session_id == Session.id)
        .where(
            Session.trace_id == target.trace_id,
            Session.org_id == current_user.org_id,
        )
        .group_by(
            Session.id,
            Session.agent_id,
            Session.parent_session_id,
            Session.trace_id,
            Session.started_at,
            Session.ended_at,
        )
        .order_by(Session.started_at.asc())
    )
    rows = chain_result.all()

    # Build tree from flat list.
    nodes: dict[uuid.UUID, ChainNode] = {}
    for row in rows:
        nodes[row.id] = ChainNode(
            id=row.id,
            agent_id=row.agent_id,
            parent_session_id=row.parent_session_id,
            trace_id=row.trace_id,
            started_at=row.started_at,
            ended_at=row.ended_at,
            event_count=row.event_count,
        )

    root: ChainNode | None = None
    for node in nodes.values():
        if node.parent_session_id is not None and node.parent_session_id in nodes:
            nodes[node.parent_session_id].children.append(node)
        else:
            root = node

    if root is None:
        root = nodes[session_id]

    return root
