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

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
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
    # Check for name collision.
    existing = await db.execute(
        select(Agent).where(Agent.name == body.name)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An agent named {body.name!r} already exists",
        )

    raw_key = security.generate_api_key()
    key_hash = security.hash_api_key(raw_key)

    agent = Agent(
        name=body.name,
        description=body.description,
        api_key_hash=key_hash,
        is_active=True,
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)

    return AgentCreateResponse(
        id=agent.id,
        name=agent.name,
        description=agent.description,
        is_active=agent.is_active,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
        api_key=raw_key,
    )


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
    limit = min(limit, 200)
    result = await db.execute(
        select(Agent)
        .where(Agent.is_active.is_(True))
        .order_by(Agent.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    agents = result.scalars().all()
    return [AgentResponse.model_validate(a) for a in agents]


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
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.is_active.is_(True))
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agent_id} not found",
        )
    return AgentResponse.model_validate(agent)


@router.delete(
    "/{agent_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate an agent",
)
async def delete_agent(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _current: Agent = Depends(get_current_agent),
) -> Response:
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
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id)
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
