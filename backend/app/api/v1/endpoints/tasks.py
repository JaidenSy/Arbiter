"""
Arbiter — API endpoints: Mission Control task queue.

Tasks are queued by org owners/admins (JWT auth) and consumed by agents
(API-key auth) which poll the queue, claim a pending task, and report
completion or failure back.

Routes:
    POST   /tasks              — queue a new task            (JWT, owner|admin)
    GET    /tasks              — list tasks for the org      (JWT)
    GET    /tasks/{id}         — read a single task          (JWT)
    PATCH  /tasks/{id}/claim   — agent claims a pending task (Agent API key)
    PATCH  /tasks/{id}/complete— agent reports outcome       (Agent API key)
    DELETE /tasks/{id}         — cancel / remove a task      (JWT, owner|admin)

The feature is gated behind the ``mission_control`` plan flag in PLAN_LIMITS;
free-tier orgs receive HTTP 402 with the usual ``plan_limit_reached`` shape.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import (
    get_current_agent,
    get_current_user,
    get_db,
    require_role,
)
from app.db.models.agent import Agent
from app.db.models.organization import Organization
from app.db.models.task import Task
from app.db.models.user import User
from app.schemas.pagination import Page
from app.schemas.task import TaskCompleteRequest, TaskCreate, TaskResponse
from app.services.plan.plan_limits import PLAN_LIMITS

router = APIRouter(prefix="/tasks", tags=["tasks"])


# ── Helpers ──────────────────────────────────────────────────────────────────

async def _require_mission_control(db: AsyncSession, org_id: uuid.UUID) -> Organization:
    """
    Load the org and 403 if its plan tier does not include mission_control.

    Mission Control is gated as a feature flag in PLAN_LIMITS — free orgs
    cannot create or interact with the queue.  Returns the loaded org so
    the caller can re-use it without a second round-trip.
    """
    org = await db.get(Organization, org_id)
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Org not found",
        )
    if not PLAN_LIMITS[org.plan_tier].get("mission_control"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Mission Control requires the Pro plan. Upgrade at /settings/billing.",
        )
    return org


# ── Endpoints (JWT — human operators) ────────────────────────────────────────


@router.post(
    "",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Queue a new task",
)
async def create_task(
    body: TaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner", "admin")),
) -> TaskResponse:
    """Queue a task for any agent in the org to pick up."""
    await _require_mission_control(db, current_user.org_id)

    task = Task(
        org_id=current_user.org_id,
        title=body.title,
        description=body.description,
        priority=body.priority,
        status="pending",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return TaskResponse.model_validate(task)


@router.get(
    "",
    response_model=Page[TaskResponse],
    summary="List tasks for the org",
)
async def list_tasks(
    status_filter: str | None = Query(
        None,
        alias="status",
        description="Filter by task status: pending | claimed | done | failed",
    ),
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Page[TaskResponse]:
    """Paginated list of tasks in the caller's org, newest first."""
    await _require_mission_control(db, current_user.org_id)

    limit = min(limit, 200)
    conditions = [Task.org_id == current_user.org_id]
    if status_filter is not None:
        conditions.append(Task.status == status_filter)

    total = await db.scalar(select(func.count(Task.id)).where(*conditions)) or 0
    result = await db.execute(
        select(Task)
        .where(*conditions)
        .order_by(Task.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    items = [TaskResponse.model_validate(t) for t in result.scalars().all()]
    return Page(items=items, total=total, skip=skip, limit=limit)


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Get a single task",
)
async def get_task(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaskResponse:
    await _require_mission_control(db, current_user.org_id)

    result = await db.execute(
        select(Task).where(
            Task.id == task_id,
            Task.org_id == current_user.org_id,
        )
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )
    return TaskResponse.model_validate(task)


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel / delete a task",
)
async def delete_task(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner", "admin")),
) -> Response:
    await _require_mission_control(db, current_user.org_id)

    result = await db.execute(
        select(Task).where(
            Task.id == task_id,
            Task.org_id == current_user.org_id,
        )
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )

    await db.delete(task)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Endpoints (Agent API key — programmatic callers) ─────────────────────────


@router.patch(
    "/{task_id}/claim",
    response_model=TaskResponse,
    summary="Agent claims a pending task",
)
async def claim_task(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_agent: Agent = Depends(get_current_agent),
) -> TaskResponse:
    """
    Atomically transition a pending task to claimed by this agent.

    Returns 409 if the task is already claimed by anyone (including self).
    Tasks are scoped to the agent's own org — cross-org claims 404.
    """
    await _require_mission_control(db, current_agent.org_id)

    result = await db.execute(
        select(Task).where(
            Task.id == task_id,
            Task.org_id == current_agent.org_id,
        )
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )

    if task.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Task {task_id} is not pending (current status: {task.status})",
        )

    task.status = "claimed"
    task.claimed_by_agent_id = current_agent.id
    task.claimed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(task)
    return TaskResponse.model_validate(task)


@router.patch(
    "/{task_id}/complete",
    response_model=TaskResponse,
    summary="Agent reports task completion",
)
async def complete_task(
    task_id: uuid.UUID,
    body: TaskCompleteRequest,
    db: AsyncSession = Depends(get_db),
    current_agent: Agent = Depends(get_current_agent),
) -> TaskResponse:
    """
    Finalise a task with status=done (default) or status=failed.

    The agent must be the one that claimed the task; tasks in done/failed
    are immutable and return 409 to prevent double-reporting.
    """
    await _require_mission_control(db, current_agent.org_id)

    result = await db.execute(
        select(Task).where(
            Task.id == task_id,
            Task.org_id == current_agent.org_id,
        )
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )

    if task.status not in ("claimed", "pending"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Task {task_id} is already {task.status}",
        )

    # Only the claiming agent (or none, if it skipped claim) can complete it.
    if (
        task.claimed_by_agent_id is not None
        and task.claimed_by_agent_id != current_agent.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Task was claimed by a different agent",
        )

    task.status = body.status
    task.output = body.output
    task.completed_at = datetime.now(timezone.utc)
    # If the agent never explicitly claimed, record itself as the worker now
    # so the audit trail still attributes the result.
    if task.claimed_by_agent_id is None:
        task.claimed_by_agent_id = current_agent.id
        if task.claimed_at is None:
            task.claimed_at = task.completed_at

    await db.commit()
    await db.refresh(task)
    return TaskResponse.model_validate(task)
