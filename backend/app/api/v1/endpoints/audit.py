"""
Arbiter API endpoints: Audit Log Export.

Streams all SessionEvent rows for an org as CSV or newline-delimited JSON,
filtered by date range.  Pro+ gated.

Routes:
    GET /audit/export: stream audit events in csv or json format
"""

from __future__ import annotations

import csv
import io
import json
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.db.models.organization import Organization
from app.db.models.user import User
from app.services.plan.plan_limits import PAID_TIERS

router = APIRouter(prefix="/audit", tags=["audit"])

_MAX_RANGE_DAYS = 90

_EXPORT_QUERY = text(
    """
    SELECT
        se.occurred_at,
        a.name  AS agent_name,
        ms.name AS mcp_server_name,
        se.tool_name,
        se.cache_hit,
        se.duration_ms,
        se.error
    FROM session_events se
    JOIN sessions s  ON se.session_id    = s.id
    JOIN agents   a  ON s.agent_id       = a.id
    LEFT JOIN mcp_servers ms ON se.mcp_server_id = ms.id
    WHERE se.org_id      = :org_id
      AND se.occurred_at >= :from_dt
      AND se.occurred_at <  :to_dt
    ORDER BY se.occurred_at ASC
    """
)


def _status(error: str | None) -> str:
    return "ok" if error is None else "error"


async def _iter_csv(db: AsyncSession, org_id, from_dt: datetime, to_dt: datetime):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "occurred_at",
            "agent_name",
            "mcp_server_name",
            "tool_name",
            "cache_hit",
            "duration_ms",
            "status",
            "error",
        ]
    )
    yield buf.getvalue()

    result = await db.stream(
        _EXPORT_QUERY,
        {"org_id": org_id, "from_dt": from_dt, "to_dt": to_dt},
    )
    async for partition in result.partitions(500):
        buf = io.StringIO()
        writer = csv.writer(buf)
        for row in partition:
            writer.writerow(
                [
                    row.occurred_at.isoformat(),
                    row.agent_name,
                    row.mcp_server_name or "",
                    row.tool_name,
                    row.cache_hit,
                    row.duration_ms,
                    _status(row.error),
                    row.error or "",
                ]
            )
        yield buf.getvalue()


async def _iter_json(db: AsyncSession, org_id, from_dt: datetime, to_dt: datetime):
    result = await db.stream(
        _EXPORT_QUERY,
        {"org_id": org_id, "from_dt": from_dt, "to_dt": to_dt},
    )
    async for partition in result.partitions(500):
        for row in partition:
            obj = {
                "occurred_at": row.occurred_at.isoformat(),
                "agent_name": row.agent_name,
                "mcp_server_name": row.mcp_server_name,
                "tool_name": row.tool_name,
                "cache_hit": row.cache_hit,
                "duration_ms": row.duration_ms,
                "status": _status(row.error),
                "error": row.error,
            }
            yield json.dumps(obj) + "\n"


@router.get(
    "/export",
    summary="Export audit log events",
    status_code=status.HTTP_200_OK,
)
async def export_audit(
    format: str = Query(..., description="csv or json"),
    from_: date = Query(..., alias="from", description="ISO date (inclusive)"),
    to: date = Query(..., description="ISO date (exclusive)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """
    Stream audit log events for the caller's org.

    - format: csv | json
    - from / to: ISO date strings; range must be ≤ 90 days
    - Requires Pro or Enterprise plan (HTTP 402 for free)
    """
    # ── Plan gate ─────────────────────────────────────────────────────────────
    org = await db.get(Organization, current_user.org_id)
    plan_tier = org.plan_tier if org else "free"
    if plan_tier not in PAID_TIERS:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Upgrade to Pro to export audit logs",
        )

    # ── Validate format ───────────────────────────────────────────────────────
    if format not in ("csv", "json"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="format must be 'csv' or 'json'",
        )

    # ── Validate date range ───────────────────────────────────────────────────
    if to < from_:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="'to' must be greater than or equal to 'from'",
        )

    if (to - from_).days > _MAX_RANGE_DAYS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Date range cannot exceed 90 days",
        )

    from_dt = datetime(from_.year, from_.month, from_.day, tzinfo=UTC)
    to_dt = datetime(to.year, to.month, to.day, tzinfo=UTC)

    # ── Stream response ───────────────────────────────────────────────────────
    if format == "csv":
        filename = f"arbiter-audit-{from_}-{to}.csv"
        return StreamingResponse(
            _iter_csv(db, current_user.org_id, from_dt, to_dt),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return StreamingResponse(
        _iter_json(db, current_user.org_id, from_dt, to_dt),
        media_type="application/json",
    )
