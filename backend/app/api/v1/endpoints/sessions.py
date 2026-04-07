"""
NexusAI — API endpoints: Sessions.

Sessions are created automatically by the proxy when a tool call is
received without a session_id.  These endpoints expose read-only access
to session history and per-session event logs for auditing.

Routes:
    GET    /sessions              — list sessions (filterable by agent_id)
    GET    /sessions/{id}         — get session with all events
    GET    /sessions/{id}/events  — get events for a session (paginated)
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import get_current_user, get_db
from app.db.models.mcp_server import MCPServer
from app.db.models.user import User
from app.db.models.session import Session, SessionEvent
from app.schemas.session import SessionEventResponse, SessionListResponse, SessionResponse

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get(
    "",
    response_model=list[SessionListResponse],
    summary="List sessions",
)
async def list_sessions(
    agent_id: uuid.UUID | None = Query(None, description="Filter by agent UUID"),
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[SessionListResponse]:
    """
    Return a paginated list of sessions, optionally filtered by agent.

    Events are NOT included in the list response for performance reasons.
    Use GET /sessions/{id} to retrieve events for a specific session.

    Args:
        agent_id: Optional filter to return only sessions for one agent.
        skip:     Pagination offset.
        limit:    Max records (capped at 200).
        db:       Injected DB session.
        _current: Auth guard.

    Returns:
        list[SessionResponse]: Sessions ordered by started_at DESC, no events.
    """
    limit = min(limit, 200)
    query = (
        select(Session)
        .where(Session.org_id == current_user.org_id)
        .order_by(Session.started_at.desc())
        .offset(skip)
        .limit(limit)
    )
    if agent_id is not None:
        query = query.where(Session.agent_id == agent_id)

    result = await db.execute(query)
    sessions = result.scalars().all()
    return [SessionListResponse.model_validate(s) for s in sessions]


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
        .options(selectinload(Session.events))
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    # Build MCP server name lookup for all server IDs referenced by events.
    server_ids = {e.mcp_server_id for e in session.events if e.mcp_server_id}
    server_map: dict[uuid.UUID, str] = {}
    if server_ids:
        servers_result = await db.execute(
            select(MCPServer.id, MCPServer.name).where(MCPServer.id.in_(server_ids))
        )
        server_map = {row.id: row.name for row in servers_result}

    # Build the response manually so we can inject mcp_server_name per event.
    session_data = SessionResponse.model_validate(session)
    enriched_events: list[SessionEventResponse] = []
    for event, schema_event in zip(session.events, session_data.events):
        schema_event.mcp_server_name = server_map.get(event.mcp_server_id)
        enriched_events.append(schema_event)
    session_data.events = enriched_events
    return session_data


@router.get(
    "/{session_id}/events",
    response_model=list[SessionEventResponse],
    summary="List events for a session",
)
async def list_session_events(
    session_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[SessionEventResponse]:
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
        list[SessionEventResponse]: Events ordered by occurred_at ASC.

    Raises:
        HTTPException 404: If the session does not exist.
    """
    # Verify the session exists first.
    session_result = await db.execute(select(Session).where(Session.id == session_id))
    if session_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    limit = min(limit, 500)
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
            select(MCPServer.id, MCPServer.name).where(MCPServer.id.in_(server_ids))
        )
        server_map = {row.id: row.name for row in servers_result}

    enriched: list[SessionEventResponse] = []
    for event in events:
        schema_event = SessionEventResponse.model_validate(event)
        schema_event.mcp_server_name = server_map.get(event.mcp_server_id)
        enriched.append(schema_event)
    return enriched
