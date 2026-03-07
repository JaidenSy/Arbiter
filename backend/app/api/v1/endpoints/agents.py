"""
NexusAI — API endpoints: Agents.

Manages agent registration and lifecycle.  API keys are generated on
creation and returned ONCE; the hash is stored, never the raw key.

Routes:
    POST   /agents          — register a new agent, returns raw API key once
    GET    /agents          — list all active agents (paginated)
    GET    /agents/{id}     — get a single agent by UUID
    DELETE /agents/{id}     — soft-delete (sets is_active=False)
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_agent, get_db
from app.db.models.agent import Agent
from app.schemas.agent import AgentCreate, AgentCreateResponse, AgentResponse

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
) -> AgentCreateResponse:
    """
    Register a new agent and return its API key.

    The API key is returned ONCE in this response.  It is not recoverable;
    if lost the agent must be deleted and re-registered.

    Args:
        body: Agent name and optional description.
        db:   Injected database session.

    Returns:
        AgentCreateResponse: Agent metadata plus the one-time raw API key.

    Raises:
        HTTPException 409: If an agent with the same name already exists.
    """
    # TODO: generate API key via security.generate_api_key()
    # TODO: hash via security.hash_api_key()
    # TODO: persist Agent row
    # TODO: return AgentCreateResponse
    raise NotImplementedError


@router.get(
    "",
    response_model=list[AgentResponse],
    summary="List all agents",
)
async def list_agents(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _current: Agent = Depends(get_current_agent),
) -> list[AgentResponse]:
    """
    Return a paginated list of all active agents.

    Args:
        skip:     Number of records to skip (offset).
        limit:    Maximum records to return (capped at 200).
        db:       Injected database session.
        _current: Auth guard — requires a valid API key.

    Returns:
        list[AgentResponse]: Active agents ordered by created_at DESC.
    """
    # TODO: SELECT * FROM agents WHERE is_active=True LIMIT limit OFFSET skip
    raise NotImplementedError


@router.get(
    "/{agent_id}",
    response_model=AgentResponse,
    summary="Get agent by ID",
)
async def get_agent(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _current: Agent = Depends(get_current_agent),
) -> AgentResponse:
    """
    Retrieve a single agent by UUID.

    Args:
        agent_id: UUID of the agent to retrieve.
        db:       Injected database session.
        _current: Auth guard.

    Returns:
        AgentResponse: The agent's metadata.

    Raises:
        HTTPException 404: If the agent does not exist or is inactive.
    """
    # TODO: fetch Agent by id, raise 404 if not found
    raise NotImplementedError


@router.delete(
    "/{agent_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate an agent",
)
async def delete_agent(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _current: Agent = Depends(get_current_agent),
) -> None:
    """
    Soft-delete an agent by setting is_active=False.

    The agent's historical sessions and events are preserved for auditing.

    Args:
        agent_id: UUID of the agent to deactivate.
        db:       Injected database session.
        _current: Auth guard.

    Raises:
        HTTPException 404: If the agent does not exist.
    """
    # TODO: set agent.is_active = False, commit
    raise NotImplementedError
