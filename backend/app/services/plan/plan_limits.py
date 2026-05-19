"""
Arbiter — Plan limit constants and quota-related exceptions.

PLAN_LIMITS is the single source of truth for per-tier resource caps.
None means unlimited (Enterprise tier).

Exceptions raised here bubble up to main.py exception handlers which
return the correct HTTP status codes and JSON shapes.
"""

from __future__ import annotations

from datetime import datetime, timezone


# ── Plan limits ───────────────────────────────────────────────────────────────

PLAN_LIMITS: dict[str, dict[str, int | None]] = {
    "free": {
        "max_agents": 3,
        "max_mcp_servers": 5,
        "max_tool_calls_mo": 1_000,
        "max_vault_secrets": 10,
    },
    "pro": {
        "max_agents": 25,
        "max_mcp_servers": 50,
        "max_tool_calls_mo": 100_000,
        "max_vault_secrets": 100,
    },
    "enterprise": {
        "max_agents": None,
        "max_mcp_servers": None,
        "max_tool_calls_mo": None,
        "max_vault_secrets": None,
    },
}

OVERAGE_GRACE_FACTOR: float = 1.05  # 5% grace on monthly tool_call quota


# ── Custom exceptions ─────────────────────────────────────────────────────────


class PlanLimitError(Exception):
    """
    Raised when an org tries to create a resource that exceeds its plan cap.

    Maps to HTTP 402.

    Attributes:
        resource:    e.g. "agents", "mcp_servers", "vault_secrets"
        current:     How many the org currently has.
        limit:       The plan cap.
        plan:        The org's plan tier string.
    """

    def __init__(
        self,
        resource: str,
        current: int,
        limit: int,
        plan: str,
    ) -> None:
        self.resource = resource
        self.current = current
        self.limit = limit
        self.plan = plan
        super().__init__(
            f"Plan limit reached: {resource} ({current}/{limit}) on {plan} plan"
        )


class QuotaExceededError(Exception):
    """
    Raised when an org's monthly tool-call quota is exhausted.

    Maps to HTTP 429.

    Attributes:
        resource:   Always "tool_calls".
        used:       Total calls made this month.
        limit:      The plan's monthly cap.
        resets_at:  ISO-8601 datetime of when the quota resets (first of next month).
    """

    def __init__(
        self,
        resource: str,
        used: int,
        limit: int,
        resets_at: datetime,
    ) -> None:
        self.resource = resource
        self.used = used
        self.limit = limit
        self.resets_at = resets_at
        super().__init__(
            f"Quota exceeded: {used}/{limit} {resource} this month"
        )


# ── Utility ───────────────────────────────────────────────────────────────────


def first_day_of_next_month() -> datetime:
    """Return midnight UTC of the first day of next month."""
    now = datetime.now(tz=timezone.utc)
    if now.month == 12:
        return now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    return now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
