"""
Unit tests for app.services.plan.plan_limits

Coverage:
    - All three plan tiers (free, pro, enterprise) have correct limit values
    - Pro vault_secrets limit is 100 (fixed from 500: coder-output deviation #1)
    - Enterprise limits are all None (unlimited)
    - PlanLimitError stores resource, current, limit, plan attributes
    - QuotaExceededError stores resource, used, limit, resets_at attributes
    - first_day_of_next_month() returns a future UTC datetime on the 1st at midnight
"""

from __future__ import annotations

from datetime import UTC, datetime

# ── PLAN_LIMITS constant tests ────────────────────────────────────────────────


class TestPlanLimitsConstants:
    def test_free_tier_max_agents(self):
        from app.services.plan.plan_limits import PLAN_LIMITS

        assert PLAN_LIMITS["free"]["max_agents"] == 2

    def test_free_tier_max_mcp_servers(self):
        from app.services.plan.plan_limits import PLAN_LIMITS

        assert PLAN_LIMITS["free"]["max_mcp_servers"] == 3

    def test_free_tier_max_tool_calls_mo(self):
        from app.services.plan.plan_limits import PLAN_LIMITS

        assert PLAN_LIMITS["free"]["max_tool_calls_mo"] == 5_000

    def test_free_tier_max_vault_secrets(self):
        from app.services.plan.plan_limits import PLAN_LIMITS

        assert PLAN_LIMITS["free"]["max_vault_secrets"] == 10

    def test_pro_tier_max_agents(self):
        from app.services.plan.plan_limits import PLAN_LIMITS

        assert PLAN_LIMITS["pro"]["max_agents"] == 25

    def test_pro_tier_max_mcp_servers(self):
        from app.services.plan.plan_limits import PLAN_LIMITS

        assert PLAN_LIMITS["pro"]["max_mcp_servers"] == 50

    def test_pro_tier_max_tool_calls_mo(self):
        from app.services.plan.plan_limits import PLAN_LIMITS

        assert PLAN_LIMITS["pro"]["max_tool_calls_mo"] == 100_000

    def test_pro_tier_max_vault_secrets_is_100_not_500(self):
        """
        Bug fix regression: pro vault_secrets was 500, fixed to 100 in coder output.
        This test will catch any future regression back to the wrong value.
        """
        from app.services.plan.plan_limits import PLAN_LIMITS

        assert PLAN_LIMITS["pro"]["max_vault_secrets"] == 100, (
            "Pro tier vault_secrets limit should be 100 (was incorrectly 500 before the fix)"
        )

    def test_enterprise_max_agents_is_none(self):
        from app.services.plan.plan_limits import PLAN_LIMITS

        assert PLAN_LIMITS["enterprise"]["max_agents"] is None

    def test_enterprise_max_mcp_servers_is_none(self):
        from app.services.plan.plan_limits import PLAN_LIMITS

        assert PLAN_LIMITS["enterprise"]["max_mcp_servers"] is None

    def test_enterprise_max_tool_calls_mo_is_none(self):
        from app.services.plan.plan_limits import PLAN_LIMITS

        assert PLAN_LIMITS["enterprise"]["max_tool_calls_mo"] is None

    def test_enterprise_max_vault_secrets_is_none(self):
        from app.services.plan.plan_limits import PLAN_LIMITS

        assert PLAN_LIMITS["enterprise"]["max_vault_secrets"] is None

    def test_all_enterprise_numeric_limits_are_none(self):
        """Numeric resource caps for enterprise must be None (unlimited). Boolean feature flags are exempt."""
        from app.services.plan.plan_limits import PLAN_LIMITS

        numeric_keys = {
            "max_agents",
            "max_mcp_servers",
            "max_tool_calls_mo",
            "max_vault_secrets",
            "max_members",
        }
        for key in numeric_keys:
            value = PLAN_LIMITS["enterprise"][key]
            assert value is None, (
                f"Enterprise limit {key!r} should be None (unlimited), got {value!r}"
            )

    def test_all_three_tiers_are_present(self):
        from app.services.plan.plan_limits import PLAN_LIMITS

        assert set(PLAN_LIMITS.keys()) == {"free", "pro", "enterprise"}

    def test_all_tiers_have_required_keys(self):
        from app.services.plan.plan_limits import PLAN_LIMITS

        required_keys = {
            "max_agents",
            "max_mcp_servers",
            "max_tool_calls_mo",
            "max_vault_secrets",
            "max_members",
            "semantic_cache",
        }
        for tier, limits in PLAN_LIMITS.items():
            assert required_keys.issubset(set(limits.keys())), (
                f"Tier {tier!r} is missing one or more required limit keys"
            )


# ── PlanLimitError tests ──────────────────────────────────────────────────────


class TestPlanLimitError:
    def test_attributes_set_correctly(self):
        from app.services.plan.plan_limits import PlanLimitError

        err = PlanLimitError(resource="agents", current=3, limit=3, plan="free")
        assert err.resource == "agents"
        assert err.current == 3
        assert err.limit == 3
        assert err.plan == "free"

    def test_str_includes_resource_and_counts(self):
        from app.services.plan.plan_limits import PlanLimitError

        err = PlanLimitError(resource="agents", current=3, limit=3, plan="free")
        msg = str(err)
        assert "agents" in msg
        assert "3" in msg
        assert "free" in msg

    def test_is_exception(self):
        from app.services.plan.plan_limits import PlanLimitError

        err = PlanLimitError(resource="mcp_servers", current=5, limit=5, plan="free")
        assert isinstance(err, Exception)


# ── QuotaExceededError tests ──────────────────────────────────────────────────


class TestQuotaExceededError:
    def test_attributes_set_correctly(self):
        from app.services.plan.plan_limits import QuotaExceededError

        resets = datetime(2026, 5, 1, 0, 0, 0, tzinfo=UTC)
        err = QuotaExceededError(resource="tool_calls", used=1050, limit=1000, resets_at=resets)
        assert err.resource == "tool_calls"
        assert err.used == 1050
        assert err.limit == 1000
        assert err.resets_at == resets

    def test_str_includes_used_and_limit(self):
        from app.services.plan.plan_limits import QuotaExceededError

        resets = datetime(2026, 5, 1, tzinfo=UTC)
        err = QuotaExceededError(resource="tool_calls", used=1050, limit=1000, resets_at=resets)
        msg = str(err)
        assert "1050" in msg
        assert "1000" in msg

    def test_is_exception(self):
        from app.services.plan.plan_limits import QuotaExceededError

        resets = datetime(2026, 5, 1, tzinfo=UTC)
        err = QuotaExceededError(resource="tool_calls", used=100, limit=100, resets_at=resets)
        assert isinstance(err, Exception)


# ── first_day_of_next_month tests ─────────────────────────────────────────────


class TestFirstDayOfNextMonth:
    def test_returns_datetime_with_utc_timezone(self):
        from app.services.plan.plan_limits import first_day_of_next_month

        result = first_day_of_next_month()
        assert result.tzinfo is not None
        assert result.tzinfo == UTC

    def test_returns_first_day_of_a_month(self):
        from app.services.plan.plan_limits import first_day_of_next_month

        result = first_day_of_next_month()
        assert result.day == 1

    def test_returns_midnight(self):
        from app.services.plan.plan_limits import first_day_of_next_month

        result = first_day_of_next_month()
        assert result.hour == 0
        assert result.minute == 0
        assert result.second == 0
        assert result.microsecond == 0

    def test_is_in_the_future(self):
        from app.services.plan.plan_limits import first_day_of_next_month

        result = first_day_of_next_month()
        assert result > datetime.now(tz=UTC)
