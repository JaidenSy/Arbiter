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
from app.core.dependencies import get_current_user, get_db
from app.db.models.agent import Agent
from app.db.models.organization import Organization
from app.db.models.user import User
from app.schemas.agent import AgentCreate, AgentCreateResponse, AgentResponse
from app.services.plan.plan_service import check_resource_limit

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
    current_user: User = Depends(get_current_user),
) -> AgentCreateResponse:
    existing = await db.execute(
        select(Agent).where(
            Agent.name == body.name,
            Agent.org_id == current_user.org_id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An agent named {body.name!r} already exists",
        )

    org = await db.get(Organization, current_user.org_id)
    await check_resource_limit(
        db=db,
        org=org,
        resource="agents",
        model=Agent,
        filter_col=Agent.org_id,
    )

    raw_key = security.generate_api_key()
    key_hash = security.hash_api_key(raw_key)

    agent = Agent(
        org_id=current_user.org_id,
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
    current_user: User = Depends(get_current_user),
) -> list[AgentResponse]:
    limit = min(limit, 200)
    result = await db.execute(
        select(Agent)
        .where(Agent.is_active.is_(True), Agent.org_id == current_user.org_id)
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


@router.delete(
    "/{agent_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate an agent",
)
async def delete_agent(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
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
