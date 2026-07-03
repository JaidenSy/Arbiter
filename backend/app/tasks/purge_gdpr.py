"""
Arbiter Background task: GDPR 30-day hard purge.

Users who exercised their Art.17 right to erasure are anonymized in place
(email → deleted-<uuid>@gdpr.invalid, is_active=False) at deletion time.
This job runs daily and hard-deletes those rows once 30 days have elapsed,
allowing the 30-day grace window required by some internal compliance policies
while still guaranteeing eventual removal.

The DB-level ON DELETE CASCADE on child tables (refresh_tokens, social_accounts,
org_invites, etc.) ensures that no orphaned child rows remain after the User
row is removed.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select

from app.db.base import async_session_factory
from app.db.models.user import User

logger = logging.getLogger(__name__)

_PURGE_INTERVAL = 86400  # 24 hours
_GDPR_GRACE_DAYS = 30


async def purge_anonymized_users() -> None:
    """
    Hard-delete anonymized users whose 30-day grace period has elapsed.

    Identifies rows where:
      - email matches the anonymized pattern  deleted-<uuid>@gdpr.invalid
      - updated_at is older than 30 days (set when the anonymization ran)

    Each matching User row is deleted; DB cascades handle child tables.
    """
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=_GDPR_GRACE_DAYS)

    async with async_session_factory() as db:
        result = await db.execute(
            delete(User).where(
                User.email.like("deleted-%@gdpr.invalid"),
                User.updated_at < cutoff,
            )
        )
        await db.commit()
        count = result.rowcount

    if count:
        logger.info("gdpr_purge: hard-deleted %d anonymized user(s) past 30-day grace window", count)
    else:
        logger.info("gdpr_purge: no anonymized users eligible for purge")


async def gdpr_purge_loop() -> None:
    """Infinite loop that runs purge_anonymized_users() once every 24 hours."""
    while True:
        await asyncio.sleep(_PURGE_INTERVAL)
        try:
            await purge_anonymized_users()
        except Exception as exc:
            logger.warning("gdpr_purge: sweep failed: %s", exc)
