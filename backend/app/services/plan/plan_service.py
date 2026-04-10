"""
NexusAI — Plan enforcement service.

Provides two check functions called from the service/endpoint layer:

    check_resource_limit  — count-based caps (agents, mcp_servers, vault_secrets)
    check_tool_call_quota — monthly rolling quota, Redis-cached

Both raise custom exceptions (plan_limits.PlanLimitError /
plan_limits.QuotaExceededError) that main.py converts to 402 / 429
responses with the canonical JSON shape.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.organization import Organization
from app.db.models.usage_event import UsageEvent
from app.services.plan.plan_limits import (
    OVERAGE_GRACE_FACTOR,
    PLAN_LIMITS,
    PlanLimitError,
    QuotaExceededError,
    first_day_of_next_month,
)


async def check_resource_limit(
    db: AsyncSession,
    org: Organization,
    resource: str,
    model,
    filter_col,
    count_active_only: bool = True,
) -> None:
    """
    Enforce a count-based plan limit before an INSERT.

    Args:
        db:               Async database session.
        org:              The organization whose limits are being checked.
        resource:         Limit key suffix, e.g. ``"agents"``, ``"mcp_servers"``,
                          ``"vault_secrets"``.  Used to look up ``max_{resource}``
                          in PLAN_LIMITS.
        model:            The SQLAlchemy ORM model to count (e.g. ``Agent``).
        filter_col:       Column expression scoping the count to this org
                          (e.g. ``Agent.org_id``).
        count_active_only: When True (default), adds ``model.is_active IS TRUE``
                          filter.  Pass False for models without an is_active
                          column (e.g. VaultSecret).

    Raises:
        PlanLimitError: When the org is at or above the plan cap.
    """
    limit = PLAN_LIMITS[org.plan_tier].get(f"max_{resource}")
    if limit is None:
        return  # enterprise = unlimited

    query = select(func.count()).where(filter_col == org.id)
    if count_active_only:
        query = query.where(model.is_active.is_(True))

    current = await db.scalar(query)
    current = current or 0

    if current >= limit:
        raise PlanLimitError(
            resource=resource,
            current=current,
            limit=limit,
            plan=org.plan_tier,
        )


async def check_tool_call_quota(
    redis,
    db: AsyncSession,
    org: Organization,
) -> None:
    """
    Enforce the monthly tool-call quota on the proxy hot path.

    Uses Redis to cache the monthly aggregate for
    ``settings.quota_cache_ttl_seconds`` (default 60 s) to avoid hitting
    Postgres on every single tool call.

    Args:
        redis: Redis client (from app.state.redis).
        db:    Async database session.
        org:   The organization making the tool call.

    Raises:
        QuotaExceededError: When usage meets or exceeds ``limit * OVERAGE_GRACE_FACTOR``.
    """
    limit = PLAN_LIMITS[org.plan_tier].get("max_tool_calls_mo")
    if limit is None:
        return  # enterprise = unlimited

    now = datetime.now(tz=timezone.utc)
    month_key = now.strftime("%Y-%m")
    cache_key = f"quota:{org.id}:tool_calls:{month_key}"

    used_cached: bytes | None = await redis.get(cache_key)

    if used_cached is None:
        # Cache miss: query DB aggregate for current calendar month.
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        used = await db.scalar(
            select(func.sum(UsageEvent.tool_calls)).where(
                UsageEvent.org_id == org.id,
                UsageEvent.event_date >= month_start.date(),
            )
        )
        used = int(used) if used is not None else 0
        await redis.setex(cache_key, settings.quota_cache_ttl_seconds, str(used))
    else:
        used = int(used_cached)

    effective_limit = int(limit * OVERAGE_GRACE_FACTOR)
    if used >= effective_limit:
        raise QuotaExceededError(
            resource="tool_calls",
            used=used,
            limit=limit,
            resets_at=first_day_of_next_month(),
        )
