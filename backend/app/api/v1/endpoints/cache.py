"""
Arbiter — API endpoints: Cache Management.

Provides visibility into and control over the semantic cache for an org.

Routes:
    GET    /cache/stats  — entry count, hit totals, top cached tools
    DELETE /cache        — flush all cache entries for the org
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.db.models.cache import CacheEntry
from app.db.models.user import User

router = APIRouter(prefix="/cache", tags=["cache"])


class CacheToolStat(BaseModel):
    tool_name: str
    entries: int


class CacheStatsResponse(BaseModel):
    total_entries: int
    expired_entries: int
    active_entries: int
    top_tools: list[CacheToolStat]


@router.get(
    "/stats",
    response_model=CacheStatsResponse,
    summary="Cache statistics for this org",
)
async def get_cache_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CacheStatsResponse:
    now = datetime.now(tz=UTC)

    total_result = await db.execute(
        select(func.count(CacheEntry.id)).where(CacheEntry.org_id == current_user.org_id)
    )
    total_entries: int = total_result.scalar_one() or 0

    expired_result = await db.execute(
        select(func.count(CacheEntry.id)).where(
            CacheEntry.org_id == current_user.org_id,
            CacheEntry.expires_at <= now,
        )
    )
    expired_entries: int = expired_result.scalar_one() or 0

    top_result = await db.execute(
        select(CacheEntry.tool_name, func.count(CacheEntry.id).label("cnt"))
        .where(CacheEntry.org_id == current_user.org_id, CacheEntry.expires_at > now)
        .group_by(CacheEntry.tool_name)
        .order_by(func.count(CacheEntry.id).desc())
        .limit(10)
    )
    top_tools = [CacheToolStat(tool_name=row.tool_name, entries=row.cnt) for row in top_result]

    return CacheStatsResponse(
        total_entries=total_entries,
        expired_entries=expired_entries,
        active_entries=total_entries - expired_entries,
        top_tools=top_tools,
    )


@router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Flush all cache entries for this org",
)
async def flush_cache(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner", "admin")),
) -> Response:
    await db.execute(delete(CacheEntry).where(CacheEntry.org_id == current_user.org_id))
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
