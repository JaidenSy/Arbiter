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
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
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
from app.services.plan.plan_service import check_resource_limit, check_tool_call_quota
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

    org = await db.get(Organization, agent.org_id)
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Org not found"
        )

    await check_tool_call_quota(redis=redis, db=db, org=org)
    service = ProxyService(db=db, redis=redis)
    return await service.forward_tool_call(request=body, agent=agent)
