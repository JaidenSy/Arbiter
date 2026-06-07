"""
Unit tests for GET /agents/{id}/risk — anomaly detection endpoint.

Three test classes:
    TestRiskScoreMath       — _build_signals() produces correct signal values
    TestRiskLevelThresholds — _score_to_level() maps scores to correct levels
    TestRiskPlanGate        — endpoint raises 402 for free-plan orgs
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

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
            total_7d=110, total_24h=10, errors_7d=10, errors_24h=5,  # spike = 1.0
            total_1h=0,     # burst = 0
            novel_count=0,  # novel = 0
            avg_dur_7d=None, avg_dur_24h=None,  # latency = 0
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
            total_7d=110, total_24h=10, errors_7d=10, errors_24h=5,  # spike = 1.0
            total_1h=1000,   # burst = 1.0 (capped)
            novel_count=10,  # novel = 1.0 (capped)
            avg_dur_7d=100.0, avg_dur_24h=250.0,  # latency = 1.0
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
    """GET /agents/{id}/risk returns 402 for free-plan orgs."""

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
            await get_agent_risk(agent_id=agent_id, db=mock_db, current_user=mock_user)

        assert exc_info.value.status_code == 402
        assert "Pro" in exc_info.value.detail

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

        mock_agent = MagicMock()
        mock_agent.id = agent_id

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # triggers 404

        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=mock_org)
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(HTTPException) as exc_info:
            await get_agent_risk(agent_id=agent_id, db=mock_db, current_user=mock_user)

        # 404 means we passed the plan gate — a 402 would mean we didn't
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
            await get_agent_risk(agent_id=agent_id, db=mock_db, current_user=mock_user)

        assert exc_info.value.status_code == 404
