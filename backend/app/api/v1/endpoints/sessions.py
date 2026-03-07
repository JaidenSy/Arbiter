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
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_agent, get_db
from app.db.models.agent import Agent
from app.schemas.session import SessionEventResponse, SessionResponse

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get(
    "",
    response_model=list[SessionResponse],
    summary="List sessions",
)
async def list_sessions(
    agent_id: uuid.UUID | None = Query(None, description="Filter by agent UUID"),
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _current: Agent = Depends(get_current_agent),
) -> list[SessionResponse]:
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
    # TODO: SELECT * FROM sessions [WHERE agent_id=?] ORDER BY started_at DESC
    raise NotImplementedError


@router.get(
    "/{session_id}",
    response_model=SessionResponse,
    summary="Get session with events",
)
async def get_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _current: Agent = Depends(get_current_agent),
) -> SessionResponse:
    """
    Return a session and all of its audit events.

    Args:
        session_id: UUID of the session to retrieve.
        db:         Injected DB session.
        _current:   Auth guard.

    Returns:
        SessionResponse: Full session with nested events list.

    Raises:
        HTTPException 404: If the session does not exist.
    """
    # TODO: SELECT session with eagerly loaded events, raise 404 if not found
    raise NotImplementedError


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
    _current: Agent = Depends(get_current_agent),
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
    # TODO: SELECT * FROM session_events WHERE session_id=? ORDER BY occurred_at
    raise NotImplementedError
