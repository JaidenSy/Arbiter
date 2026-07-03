"""
Unit tests for GET /agents/{id}/risk: anomaly detection endpoint.

Five test classes:
    TestRiskScoreMath      : _build_signals() produces correct signal values
    TestRiskLevelThresholds: _score_to_level() maps scores to correct levels
    TestRiskPlanGate       : endpoint raises 402 for free-plan orgs / 500 for missing org
    TestRiskSignalBoundaries: edge cases: exact-2× thresholds, zero-baseline burst, full off-hours
    TestRiskEndpointHappyPath: full endpoint pipeline with mocked DB, verifies response shape+score
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _make_mock_redis(cached: bytes | None = None) -> AsyncMock:
    """Return a mock Redis client. Defaults to cache miss (get returns None)."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=cached)
    redis.setex = AsyncMock(return_value=True)
    return redis


def _signals(**kwargs):
    """Call _build_signals with sensible defaults, overriding specified fields."""
    from app.api.v1.endpoints.agents import _build_signals

    defaults = dict(
        total_7d=0,
        total_24h=0,
        total_1h=0,
        errors_7d=0,
        errors_24h=0,
        avg_dur_7d=None,
        avg_dur_24h=None,
        off_hours_24h=0,
        novel_count=0,
    )
    defaults.update(kwargs)
    return _build_signals(**defaults)


# ─────────────────────────────────────────────────────────────────────────────
# TestRiskScoreMath
# ─────────────────────────────────────────────────────────────────────────────


class TestRiskScoreMath:
    """_build_signals() produces correct normalised signal values."""

    def test_no_activity_all_signals_zero(self):
        s = _signals()
        assert s.error_rate_spike == 0.0
        assert s.burst_ratio == 0.0
        assert s.novel_tool_count == 0.0
        assert s.latency_spike_ratio == 0.0
        assert s.off_hours_ratio_24h == 0.0

    def test_error_spike_fires_when_24h_rate_exceeds_2x_baseline(self):
        # Baseline: 100 calls, 5 errors (5% rate)
        # 24h: 10 calls, 5 errors (50% rate) → 10× baseline → spike
        s = _signals(
            total_7d=110,
            total_24h=10,
            errors_7d=10,
            errors_24h=5,
        )
        assert s.error_rate_spike == 1.0

    def test_error_spike_does_not_fire_when_rate_below_threshold(self):
        # Baseline: 100 calls, 10 errors (10%)
        # 24h: 10 calls, 1 error (10%) → exactly equal, not > 2×
        s = _signals(
            total_7d=110,
            total_24h=10,
            errors_7d=11,
            errors_24h=1,
        )
        assert s.error_rate_spike == 0.0

    def test_error_spike_fires_when_baseline_is_zero_and_24h_has_errors(self):
        # No errors in prior 6 days, any errors in 24h = spike
        s = _signals(
            total_7d=10,
            total_24h=10,
            errors_7d=1,
            errors_24h=1,
        )
        # baseline errors = 0, rate_baseline = 0 → rate_24h (10%) > 2×0
        assert s.error_rate_spike == 1.0

    def test_burst_ratio_zero_when_no_activity(self):
        s = _signals(total_7d=0, total_1h=0)
        assert s.burst_ratio == 0.0

    def test_burst_ratio_capped_at_1_when_extremely_high(self):
        # 168h avg = 1 call/h; last hour = 1000 calls → 1000× → capped at 1.0
        s = _signals(total_7d=168, total_1h=1000)
        assert s.burst_ratio == 1.0

    def test_burst_ratio_partial_value(self):
        # 7d total = 168, hourly avg = 1.0; last 1h = 5 → raw = 5, /10 = 0.5
        s = _signals(total_7d=168, total_1h=5)
        assert abs(s.burst_ratio - 0.5) < 0.001

    def test_novel_tool_count_zero_when_no_novel_tools(self):
        s = _signals(novel_count=0)
        assert s.novel_tool_count == 0.0

    def test_novel_tool_count_capped_at_1_when_5_or_more(self):
        s = _signals(novel_count=5)
        assert s.novel_tool_count == 1.0

        s2 = _signals(novel_count=100)
        assert s2.novel_tool_count == 1.0

    def test_novel_tool_count_partial(self):
        s = _signals(novel_count=2)
        assert abs(s.novel_tool_count - 0.4) < 0.001

    def test_latency_spike_fires_when_24h_avg_exceeds_2x_7d_avg(self):
        # 7d avg = 100ms, 24h avg = 250ms → 2.5× → spike
        s = _signals(avg_dur_7d=100.0, avg_dur_24h=250.0)
        assert s.latency_spike_ratio == 1.0

    def test_latency_spike_does_not_fire_when_within_threshold(self):
        # 7d avg = 100ms, 24h avg = 190ms → 1.9× → no spike
        s = _signals(avg_dur_7d=100.0, avg_dur_24h=190.0)
        assert s.latency_spike_ratio == 0.0

    def test_latency_spike_zero_when_no_duration_data(self):
        s = _signals(avg_dur_7d=None, avg_dur_24h=None)
        assert s.latency_spike_ratio == 0.0

    def test_off_hours_ratio_equals_fraction_of_24h_calls(self):
        # 4 off-hours calls out of 10 total → 0.4
        s = _signals(total_24h=10, off_hours_24h=4)
        assert abs(s.off_hours_ratio_24h - 0.4) < 0.001

    def test_off_hours_ratio_zero_when_no_24h_calls(self):
        s = _signals(total_24h=0, off_hours_24h=0)
        assert s.off_hours_ratio_24h == 0.0

    def test_weighted_score_is_sum_of_signal_times_weight(self):
        from app.api.v1.endpoints.agents import _RISK_WEIGHTS

        s = _signals(
            total_7d=110,
            total_24h=10,
            errors_7d=10,
            errors_24h=5,  # spike = 1.0
            total_1h=0,  # burst = 0
            novel_count=0,  # novel = 0
            avg_dur_7d=None,
            avg_dur_24h=None,  # latency = 0
            off_hours_24h=0,  # off_hours = 0
        )
        # Only error_rate_spike fires (1.0 × 0.35)
        expected = round(1.0 * _RISK_WEIGHTS["error_rate_spike"], 4)
        score = round(
            s.error_rate_spike * _RISK_WEIGHTS["error_rate_spike"]
            + s.burst_ratio * _RISK_WEIGHTS["burst_ratio"]
            + s.novel_tool_count * _RISK_WEIGHTS["novel_tool_count"]
            + s.latency_spike_ratio * _RISK_WEIGHTS["latency_spike_ratio"]
            + s.off_hours_ratio_24h * _RISK_WEIGHTS["off_hours_ratio_24h"],
            4,
        )
        assert abs(score - expected) < 0.0001

    def test_all_signals_at_max_score_is_1(self):
        from app.api.v1.endpoints.agents import _RISK_WEIGHTS

        s = _signals(
            total_7d=110,
            total_24h=10,
            errors_7d=10,
            errors_24h=5,  # spike = 1.0
            total_1h=1000,  # burst = 1.0 (capped)
            novel_count=10,  # novel = 1.0 (capped)
            avg_dur_7d=100.0,
            avg_dur_24h=250.0,  # latency = 1.0
            off_hours_24h=10,  # off_hours = 1.0 (all 10 out of 10)
        )
        score = (
            s.error_rate_spike * _RISK_WEIGHTS["error_rate_spike"]
            + s.burst_ratio * _RISK_WEIGHTS["burst_ratio"]
            + s.novel_tool_count * _RISK_WEIGHTS["novel_tool_count"]
            + s.latency_spike_ratio * _RISK_WEIGHTS["latency_spike_ratio"]
            + s.off_hours_ratio_24h * _RISK_WEIGHTS["off_hours_ratio_24h"]
        )
        assert abs(score - 1.0) < 0.001


# ─────────────────────────────────────────────────────────────────────────────
# TestRiskLevelThresholds
# ─────────────────────────────────────────────────────────────────────────────


class TestRiskLevelThresholds:
    """_score_to_level() maps scores to the correct named levels."""

    def test_zero_score_is_low(self):
        from app.api.v1.endpoints.agents import _score_to_level

        assert _score_to_level(0.0) == "low"

    def test_below_0_25_is_low(self):
        from app.api.v1.endpoints.agents import _score_to_level

        assert _score_to_level(0.24) == "low"

    def test_0_25_is_medium(self):
        from app.api.v1.endpoints.agents import _score_to_level

        assert _score_to_level(0.25) == "medium"

    def test_0_49_is_medium(self):
        from app.api.v1.endpoints.agents import _score_to_level

        assert _score_to_level(0.49) == "medium"

    def test_0_50_is_high(self):
        from app.api.v1.endpoints.agents import _score_to_level

        assert _score_to_level(0.50) == "high"

    def test_0_74_is_high(self):
        from app.api.v1.endpoints.agents import _score_to_level

        assert _score_to_level(0.74) == "high"

    def test_0_75_is_critical(self):
        from app.api.v1.endpoints.agents import _score_to_level

        assert _score_to_level(0.75) == "critical"

    def test_1_0_is_critical(self):
        from app.api.v1.endpoints.agents import _score_to_level

        assert _score_to_level(1.0) == "critical"


# ─────────────────────────────────────────────────────────────────────────────
# TestRiskPlanGate
# ─────────────────────────────────────────────────────────────────────────────


class TestRiskPlanGate:
    """GET /agents/{id}/risk returns 402 for non-pro/enterprise orgs."""

    @pytest.mark.asyncio
    async def test_free_plan_raises_402(self):
        from fastapi import HTTPException

        from app.api.v1.endpoints.agents import get_agent_risk

        agent_id = uuid.uuid4()

        mock_org = MagicMock()
        mock_org.plan_tier = "free"

        mock_user = MagicMock()
        mock_user.org_id = uuid.uuid4()

        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=mock_org)

        with pytest.raises(HTTPException) as exc_info:
            await get_agent_risk(
                agent_id=agent_id, db=mock_db, redis=_make_mock_redis(), current_user=mock_user
            )

        assert exc_info.value.status_code == 402
        assert "Pro" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_unknown_plan_raises_402(self):
        """Any unrecognised tier (e.g. future 'starter') is denied, not silently granted."""
        from fastapi import HTTPException

        from app.api.v1.endpoints.agents import get_agent_risk

        agent_id = uuid.uuid4()

        mock_org = MagicMock()
        mock_org.plan_tier = "starter"

        mock_user = MagicMock()
        mock_user.org_id = uuid.uuid4()

        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=mock_org)

        with pytest.raises(HTTPException) as exc_info:
            await get_agent_risk(
                agent_id=agent_id, db=mock_db, redis=_make_mock_redis(), current_user=mock_user
            )

        assert exc_info.value.status_code == 402

    @pytest.mark.asyncio
    async def test_pro_plan_does_not_raise_plan_error(self):
        """Pro plan passes the plan gate (may raise 404 due to mock, not 402)."""
        from fastapi import HTTPException

        from app.api.v1.endpoints.agents import get_agent_risk

        agent_id = uuid.uuid4()

        mock_org = MagicMock()
        mock_org.plan_tier = "pro"

        mock_user = MagicMock()
        mock_user.org_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # triggers 404

        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=mock_org)
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(HTTPException) as exc_info:
            await get_agent_risk(
                agent_id=agent_id, db=mock_db, redis=_make_mock_redis(), current_user=mock_user
            )

        # 404 means we passed the plan gate: a 402 would mean we didn't
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_enterprise_plan_does_not_raise_plan_error(self):
        """Enterprise plan passes the plan gate (may raise 404 due to mock, not 402)."""
        from fastapi import HTTPException

        from app.api.v1.endpoints.agents import get_agent_risk

        agent_id = uuid.uuid4()

        mock_org = MagicMock()
        mock_org.plan_tier = "enterprise"

        mock_user = MagicMock()
        mock_user.org_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=mock_org)
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(HTTPException) as exc_info:
            await get_agent_risk(
                agent_id=agent_id, db=mock_db, redis=_make_mock_redis(), current_user=mock_user
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_org_not_found_returns_500(self):
        """When db.get(Organization) returns None the endpoint raises 500, not 402/404."""
        from fastapi import HTTPException

        from app.api.v1.endpoints.agents import get_agent_risk

        agent_id = uuid.uuid4()

        mock_user = MagicMock()
        mock_user.org_id = uuid.uuid4()

        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await get_agent_risk(
                agent_id=agent_id, db=mock_db, redis=_make_mock_redis(), current_user=mock_user
            )

        assert exc_info.value.status_code == 500


# ─────────────────────────────────────────────────────────────────────────────
# TestRiskSignalBoundaries
# ─────────────────────────────────────────────────────────────────────────────


class TestRiskSignalBoundaries:
    """Edge cases: exact-2× thresholds (strictly >), zero-baseline burst, full off-hours."""

    def test_error_spike_exactly_2x_baseline_does_not_fire(self):
        # Condition is rate_24h > 2.0 * rate_baseline (strictly greater).
        # baseline: 100 calls, 10 errors (10%); 24h: 10 calls, 2 errors (20%) = exactly 2×.
        s = _signals(
            total_7d=110,
            total_24h=10,
            errors_7d=12,
            errors_24h=2,
        )
        assert s.error_rate_spike == 0.0

    def test_latency_spike_exactly_2x_baseline_does_not_fire(self):
        # avg_dur_24h == 2.0 * avg_dur_7d: strictly not greater, so no spike.
        s = _signals(avg_dur_7d=100.0, avg_dur_24h=200.0)
        assert s.latency_spike_ratio == 0.0

    def test_burst_from_zero_7d_baseline_is_capped_at_1(self):
        # total_7d=0 → hourly_avg=0.0 → raw_burst = total_1h / 0.001 (large) → capped 1.0
        s = _signals(total_7d=0, total_1h=1)
        assert s.burst_ratio == 1.0

    def test_off_hours_fully_saturated_equals_1(self):
        # All calls in the 24h window fall outside business hours.
        s = _signals(total_24h=10, off_hours_24h=10)
        assert abs(s.off_hours_ratio_24h - 1.0) < 0.001

    def test_novel_tool_count_exactly_at_cap_is_1(self):
        # novel_count / 5 == 1.0 exactly (not >1 before the min).
        s = _signals(novel_count=5)
        assert s.novel_tool_count == 1.0

    def test_error_spike_just_above_2x_fires(self):
        # baseline 100 calls, 10 errors (10%); 24h: 10 calls, 3 errors (30%) > 20% → fires
        s = _signals(
            total_7d=110,
            total_24h=10,
            errors_7d=13,
            errors_24h=3,
        )
        assert s.error_rate_spike == 1.0


# ─────────────────────────────────────────────────────────────────────────────
# TestRiskEndpointHappyPath
# ─────────────────────────────────────────────────────────────────────────────


class TestRiskEndpointHappyPath:
    """Full endpoint pipeline with mocked DB: verifies response shape and score."""

    @staticmethod
    def _make_stats_mock(data: dict) -> MagicMock:
        m = MagicMock()
        m.mappings.return_value.one.return_value = data
        return m

    @pytest.mark.asyncio
    async def test_zero_activity_returns_score_0_and_level_low(self):
        from app.api.v1.endpoints.agents import get_agent_risk

        agent_id = uuid.uuid4()

        mock_org = MagicMock()
        mock_org.plan_tier = "pro"

        mock_user = MagicMock()
        mock_user.org_id = uuid.uuid4()

        mock_agent_result = MagicMock()
        mock_agent_result.scalar_one_or_none.return_value = MagicMock(id=agent_id)

        stats_data = {
            "total_7d": 0,
            "total_24h": 0,
            "total_1h": 0,
            "errors_7d": 0,
            "errors_24h": 0,
            "avg_dur_7d": None,
            "avg_dur_24h": None,
            "off_hours_24h": 0,
        }
        novel_data = {"novel_tool_count": 0}

        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=mock_org)
        mock_db.execute = AsyncMock(
            side_effect=[
                mock_agent_result,
                self._make_stats_mock(stats_data),
                self._make_stats_mock(novel_data),
            ]
        )

        response = await get_agent_risk(
            agent_id=agent_id, db=mock_db, redis=_make_mock_redis(), current_user=mock_user
        )

        assert response.agent_id == agent_id
        assert response.score == 0.0
        assert response.level == "low"
        assert response.signals.error_rate_spike == 0.0
        assert response.signals.burst_ratio == 0.0
        assert response.signals.novel_tool_count == 0.0
        assert response.signals.latency_spike_ratio == 0.0
        assert response.signals.off_hours_ratio_24h == 0.0

    @pytest.mark.asyncio
    async def test_only_error_spike_fires_score_equals_weight(self):
        """When only error_rate_spike fires, score == its weight (0.35)."""
        from app.api.v1.endpoints.agents import _RISK_WEIGHTS, get_agent_risk

        agent_id = uuid.uuid4()

        mock_org = MagicMock()
        mock_org.plan_tier = "enterprise"

        mock_user = MagicMock()
        mock_user.org_id = uuid.uuid4()

        mock_agent_result = MagicMock()
        mock_agent_result.scalar_one_or_none.return_value = MagicMock(id=agent_id)

        # 24h error rate (50%) is 10× baseline (5%) → spike fires; nothing else triggers.
        stats_data = {
            "total_7d": 110,
            "total_24h": 10,
            "total_1h": 0,
            "errors_7d": 10,
            "errors_24h": 5,  # baseline 5/100=5%, 24h 5/10=50%
            "avg_dur_7d": None,
            "avg_dur_24h": None,
            "off_hours_24h": 0,
        }
        novel_data = {"novel_tool_count": 0}

        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=mock_org)
        mock_db.execute = AsyncMock(
            side_effect=[
                mock_agent_result,
                self._make_stats_mock(stats_data),
                self._make_stats_mock(novel_data),
            ]
        )

        response = await get_agent_risk(
            agent_id=agent_id, db=mock_db, redis=_make_mock_redis(), current_user=mock_user
        )

        expected_score = round(_RISK_WEIGHTS["error_rate_spike"], 4)
        assert abs(response.score - expected_score) < 0.0001
        assert response.level == "medium"  # 0.35 >= 0.25

    @pytest.mark.asyncio
    async def test_response_agent_id_matches_requested_agent_id(self):
        """agent_id in response must equal the requested agent_id."""
        from app.api.v1.endpoints.agents import get_agent_risk

        agent_id = uuid.uuid4()

        mock_org = MagicMock()
        mock_org.plan_tier = "pro"

        mock_user = MagicMock()
        mock_user.org_id = uuid.uuid4()

        mock_agent_result = MagicMock()
        mock_agent_result.scalar_one_or_none.return_value = MagicMock(id=agent_id)

        stats_data = {
            "total_7d": 0,
            "total_24h": 0,
            "total_1h": 0,
            "errors_7d": 0,
            "errors_24h": 0,
            "avg_dur_7d": None,
            "avg_dur_24h": None,
            "off_hours_24h": 0,
        }
        novel_data = {"novel_tool_count": 0}

        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=mock_org)
        mock_db.execute = AsyncMock(
            side_effect=[
                mock_agent_result,
                self._make_stats_mock(stats_data),
                self._make_stats_mock(novel_data),
            ]
        )

        response = await get_agent_risk(
            agent_id=agent_id, db=mock_db, redis=_make_mock_redis(), current_user=mock_user
        )

        assert response.agent_id == agent_id
