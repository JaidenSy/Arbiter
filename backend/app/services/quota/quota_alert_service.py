"""
Arbiter Quota alert service.

Runs once per hour. For every active org it:
  1. Sums tool_calls for the current billing month from usage_events.
  2. Compares against the plan limit (skips enterprise: unlimited).
  3. Sends an 80% warning email when usage crosses 80% (once per month).
  4. Sends a 100% exceeded email when usage hits 100% (once per month).
  5. Resets both flags on the first of each month before checking.

Uses a single JOIN query so the check scales to many orgs without N+1 DB hits.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.base import async_session_factory
from app.db.models.org_membership import OrgMembership
from app.db.models.organization import Organization
from app.db.models.usage_event import UsageEvent
from app.db.models.user import User
from app.services.email.email_service import send_email
from app.services.plan.plan_limits import PLAN_LIMITS

logger = logging.getLogger(__name__)

_ALERT_INTERVAL = 3600  # 1 hour


def _billing_url() -> str:
    return f"{settings.frontend_url}/billing"


def _make_80_email(org_name: str, used: int, limit: int) -> tuple[str, str]:
    billing = _billing_url()
    subject = "You've used 80% of your Arbiter tool-call quota"
    html = f"""
<p>Hi,</p>
<p>Your organization <strong>{org_name}</strong> has used <strong>{used:,}</strong>
of its <strong>{limit:,}</strong> monthly tool calls: that's 80% of your plan quota.</p>
<p>Upgrade to Pro or Enterprise to avoid hitting your limit and keep tool calls running smoothly.</p>
<p><a href="{billing}" style="
  display:inline-block;padding:10px 20px;background:#f59e0b;color:#fff;
  text-decoration:none;border-radius:6px;font-weight:bold;">Upgrade now</a></p>
<p>The Arbiter team</p>
"""
    return subject, html


def _make_100_email(org_name: str, used: int, limit: int) -> tuple[str, str]:
    billing = _billing_url()
    subject = "Arbiter quota reached: tool calls paused"
    html = f"""
<p>Hi,</p>
<p>Your organization <strong>{org_name}</strong> has reached its monthly limit of
<strong>{limit:,}</strong> tool calls.</p>
<p>Tool calls are now returning <strong>429 errors</strong> until you upgrade or your quota resets
on the first of next month.</p>
<p><a href="{billing}" style="
  display:inline-block;padding:10px 20px;background:#ef4444;color:#fff;
  text-decoration:none;border-radius:6px;font-weight:bold;">Upgrade now</a></p>
<p>The Arbiter team</p>
"""
    return subject, html


async def check_and_send_quota_alerts(db: AsyncSession) -> None:
    """
    Run once per hour. Checks quota for every active org in a single DB pass.

    Enterprise orgs (max_tool_calls_mo=None) are skipped: they have no cap.
    If today is the 1st of the month, both alert flags are reset first.
    """
    now = datetime.now(tz=UTC)
    today = now.date()
    first_of_month = today.replace(day=1)

    # ── Reset flags on first of the month ────────────────────────────────────
    if today.day == 1:
        await db.execute(
            update(Organization)
            .where(Organization.is_active.is_(True))
            .values(quota_alert_80_sent=False, quota_alert_100_sent=False)
        )
        await db.flush()
        logger.info("quota_alerts: reset alert flags for new billing month")

    # ── Single-pass query: orgs + owner email + monthly usage ─────────────────
    # Subquery: sum tool_calls per org for the current month.
    monthly_usage_sq = (
        select(
            UsageEvent.org_id,
            func.coalesce(func.sum(UsageEvent.tool_calls), 0).label("monthly_calls"),
        )
        .where(UsageEvent.event_date >= first_of_month)
        .group_by(UsageEvent.org_id)
        .subquery()
    )

    # Join organizations → owner user → monthly usage (left join so orgs with
    # zero calls this month still appear).
    stmt = (
        select(
            Organization.id,
            Organization.name,
            Organization.plan_tier,
            Organization.quota_alert_80_sent,
            Organization.quota_alert_100_sent,
            User.email.label("owner_email"),
            func.coalesce(monthly_usage_sq.c.monthly_calls, 0).label("monthly_calls"),
        )
        # Owners resolved via memberships: users.org_id/role only reflect the
        # org a user currently has active, not every org they own.
        .join(
            OrgMembership,
            (OrgMembership.org_id == Organization.id) & (OrgMembership.role == "owner"),
        )
        .join(User, (User.id == OrgMembership.user_id) & (User.is_active.is_(True)))
        .outerjoin(monthly_usage_sq, monthly_usage_sq.c.org_id == Organization.id)
        .where(Organization.is_active.is_(True))
    )

    rows = (await db.execute(stmt)).all()

    alerts_sent = 0
    for row in rows:
        plan_limit = PLAN_LIMITS.get(row.plan_tier, {}).get("max_tool_calls_mo")
        if plan_limit is None:
            # Enterprise: unlimited, skip.
            continue

        used: int = row.monthly_calls
        pct = used / plan_limit if plan_limit > 0 else 0.0

        org_id = row.id
        org_name = row.name
        owner_email = row.owner_email

        if pct >= 1.0 and not row.quota_alert_100_sent:
            subject, html = _make_100_email(org_name, used, plan_limit)
            try:
                await send_email(owner_email, subject, html)
                await db.execute(
                    update(Organization)
                    .where(Organization.id == org_id)
                    .values(quota_alert_100_sent=True)
                )
                alerts_sent += 1
                logger.info(
                    "quota_alerts: sent 100%% alert to %s (org=%s used=%d/%d)",
                    owner_email,
                    org_id,
                    used,
                    plan_limit,
                )
            except Exception as exc:
                logger.warning(
                    "quota_alerts: failed to send 100%% alert to %s: %s", owner_email, exc
                )

        elif pct >= 0.8 and not row.quota_alert_80_sent:
            subject, html = _make_80_email(org_name, used, plan_limit)
            try:
                await send_email(owner_email, subject, html)
                await db.execute(
                    update(Organization)
                    .where(Organization.id == org_id)
                    .values(quota_alert_80_sent=True)
                )
                alerts_sent += 1
                logger.info(
                    "quota_alerts: sent 80%% alert to %s (org=%s used=%d/%d)",
                    owner_email,
                    org_id,
                    used,
                    plan_limit,
                )
            except Exception as exc:
                logger.warning(
                    "quota_alerts: failed to send 80%% alert to %s: %s", owner_email, exc
                )

    await db.commit()

    logger.info(
        "quota_alerts: checked %d org(s), sent %d alert(s)",
        len(rows),
        alerts_sent,
    )


async def quota_alert_loop() -> None:
    """Infinite loop: run check_and_send_quota_alerts once per hour."""
    while True:
        await asyncio.sleep(_ALERT_INTERVAL)
        try:
            async with async_session_factory() as db:
                await check_and_send_quota_alerts(db)
        except Exception as exc:
            logger.warning("quota_alerts: sweep failed: %s", exc)
