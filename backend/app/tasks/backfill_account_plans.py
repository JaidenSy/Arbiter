"""
Arbiter — One-off task: grandfather paid orgs onto owner accounts.

Run this once, immediately after ``alembic upgrade head`` brings in migration
035 (account-level billing columns) and **before** flipping
``ACCOUNT_BILLING_ENABLED`` on. It copies every paid org's plan + Stripe linkage
up onto its owner account so the account-derived effective plan matches the
legacy org plan (parity), with a never-downgrade guarantee.

Idempotent — safe to re-run. At launch the paid set is ~empty so it is a no-op,
but running it is the documented, auditable step that keeps an early paying
customer whole if a subscription lands before the cutover.

Usage:
    python -m app.tasks.backfill_account_plans
"""

from __future__ import annotations

import asyncio
import logging

from app.db.base import async_session_factory
from app.services.plan.account_plan import backfill_account_plans

logger = logging.getLogger(__name__)


async def run() -> int:
    """Run the backfill in a single transaction and commit. Returns rows changed."""
    async with async_session_factory() as db:
        changed = await backfill_account_plans(db)
        await db.commit()
    return changed


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    changed = asyncio.run(run())
    print(f"backfill_account_plans: {changed} account(s) grandfathered")


if __name__ == "__main__":
    main()
