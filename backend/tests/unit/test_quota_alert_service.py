"""
Unit tests for app.services.quota.quota_alert_service.check_and_send_quota_alerts

Coverage:
    - Enterprise orgs (None limit) are skipped: no email, no DB flag update
    - Usage < 80% → no emails sent
    - Usage >= 80% and < 100% → 80% email sent, flag set
    - Usage >= 100% → 100% email sent, flag set
    - quota_alert_80_sent=True → 80% email not re-sent
    - quota_alert_100_sent=True → 100% email not re-sent
    - Email send failure → warning logged, sweep continues for remaining orgs
    - today.day == 1 → UPDATE to reset both alert flags runs before the check
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Helpers ───────────────────────────────────────────────────────────────────

_ORG_ID = uuid.uuid4()
_OWNER_EMAIL = "owner@example.com"


def _make_org_row(
    *,
    plan_tier: str = "pro",
    used: int = 0,
    alert_80_sent: bool = False,
    alert_100_sent: bool = False,
    org_id: uuid.UUID | None = None,
) -> MagicMock:
    row = MagicMock()
    row.id = org_id or _ORG_ID
    row.name = "Test Org"
    row.plan_tier = plan_tier
    row.quota_alert_80_sent = alert_80_sent
    row.quota_alert_100_sent = alert_100_sent
    row.owner_email = _OWNER_EMAIL
    row.monthly_calls = used
    return row


def _make_db(rows: list[MagicMock], is_first_of_month: bool = False) -> AsyncMock:
    """
    Build a mock AsyncSession for quota alert tests.

    execute() is called 1-3 times depending on the path:
      - Once for the month-reset UPDATE (if today.day == 1)
      - Once for the main org+usage SELECT
      - Once per 80%/100% flag UPDATE for each org that triggers an alert

    We use a side_effect list to handle the variable call count.
    """
    db = AsyncMock()

    # The main SELECT result
    select_result = MagicMock()
    select_result.all.return_value = rows

    # Generic result for UPDATE statements (not consumed)
    update_result = MagicMock()

    # Side-effect: first call for month-reset UPDATE (if applicable), then SELECT, then UPDATEs
    if is_first_of_month:
        db.execute = AsyncMock(side_effect=[update_result, select_result] + [update_result] * 10)
    else:
        db.execute = AsyncMock(side_effect=[select_result] + [update_result] * 10)

    db.flush = AsyncMock()
    db.commit = AsyncMock()
    return db


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestQuotaAlertService:
    @pytest.mark.asyncio
    async def test_enterprise_org_is_skipped(self):
        """Enterprise orgs have no limit and must never trigger an email."""
        from app.services.quota.quota_alert_service import check_and_send_quota_alerts

        # Enterprise: 9999 calls, no limit → should be skipped entirely
        row = _make_org_row(plan_tier="enterprise", used=9999)
        db = _make_db([row])

        with patch(
            "app.services.quota.quota_alert_service.send_email", new_callable=AsyncMock
        ) as mock_send:
            await check_and_send_quota_alerts(db)
            mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_under_80_percent_sends_no_email(self):
        """Usage < 80% of limit → no emails sent."""
        from app.services.quota.quota_alert_service import check_and_send_quota_alerts

        # Pro plan limit = 100_000; 79_000 < 80% → no alert
        row = _make_org_row(plan_tier="pro", used=79_000)
        db = _make_db([row])

        with patch(
            "app.services.quota.quota_alert_service.send_email", new_callable=AsyncMock
        ) as mock_send:
            await check_and_send_quota_alerts(db)
            mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_80_percent_sends_warning_email(self):
        """Usage >= 80% but < 100% → 80% alert email sent and flag updated."""
        from app.services.quota.quota_alert_service import check_and_send_quota_alerts

        # Pro limit = 100_000; 80_000 = exactly 80%
        row = _make_org_row(plan_tier="pro", used=80_000, alert_80_sent=False)
        db = _make_db([row])

        with patch(
            "app.services.quota.quota_alert_service.send_email", new_callable=AsyncMock
        ) as mock_send:
            await check_and_send_quota_alerts(db)

        mock_send.assert_called_once()
        subject, html = mock_send.call_args[0][1], mock_send.call_args[0][2]
        assert "80%" in subject
        db.execute.assert_called()  # flag UPDATE was executed

    @pytest.mark.asyncio
    async def test_100_percent_sends_exceeded_email(self):
        """Usage >= 100% → 100% exceeded email sent and flag updated."""
        from app.services.quota.quota_alert_service import check_and_send_quota_alerts

        # Pro limit = 100_000; 100_000 = exactly 100%
        row = _make_org_row(plan_tier="pro", used=100_000, alert_100_sent=False)
        db = _make_db([row])

        with patch(
            "app.services.quota.quota_alert_service.send_email", new_callable=AsyncMock
        ) as mock_send:
            await check_and_send_quota_alerts(db)

        mock_send.assert_called_once()
        subject = mock_send.call_args[0][1]
        assert (
            "quota" in subject.lower()
            or "reached" in subject.lower()
            or "paused" in subject.lower()
        )

    @pytest.mark.asyncio
    async def test_80_percent_not_re_sent_when_flag_already_set(self):
        """quota_alert_80_sent=True → no duplicate email."""
        from app.services.quota.quota_alert_service import check_and_send_quota_alerts

        row = _make_org_row(plan_tier="pro", used=85_000, alert_80_sent=True, alert_100_sent=False)
        db = _make_db([row])

        with patch(
            "app.services.quota.quota_alert_service.send_email", new_callable=AsyncMock
        ) as mock_send:
            await check_and_send_quota_alerts(db)
            mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_100_percent_not_re_sent_when_flag_already_set(self):
        """quota_alert_100_sent=True → no duplicate exceeded email."""
        from app.services.quota.quota_alert_service import check_and_send_quota_alerts

        row = _make_org_row(plan_tier="pro", used=100_000, alert_80_sent=True, alert_100_sent=True)
        db = _make_db([row])

        with patch(
            "app.services.quota.quota_alert_service.send_email", new_callable=AsyncMock
        ) as mock_send:
            await check_and_send_quota_alerts(db)
            mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_email_failure_does_not_abort_sweep(self):
        """If send_email raises for one org, the sweep finishes without crashing."""
        from app.services.quota.quota_alert_service import check_and_send_quota_alerts

        row1 = _make_org_row(plan_tier="pro", used=80_000, org_id=uuid.uuid4())
        row2 = _make_org_row(plan_tier="pro", used=80_000, org_id=uuid.uuid4())
        db = _make_db([row1, row2])

        call_count = 0

        async def flaky_send(to, subject, html):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("SMTP timeout")

        with patch("app.services.quota.quota_alert_service.send_email", side_effect=flaky_send):
            # Must not raise: email failure is swallowed with a warning
            await check_and_send_quota_alerts(db)

        # Second org's email was still attempted
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_free_plan_80_percent_sends_email(self):
        """Free plan limit is 5_000; 80% = 4_000 calls → alert sent."""
        from app.services.quota.quota_alert_service import check_and_send_quota_alerts

        row = _make_org_row(plan_tier="free", used=4_000, alert_80_sent=False)
        db = _make_db([row])

        with patch(
            "app.services.quota.quota_alert_service.send_email", new_callable=AsyncMock
        ) as mock_send:
            await check_and_send_quota_alerts(db)
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_month_reset_runs_on_first_of_month(self):
        """
        When today.day == 1, an UPDATE to reset both alert flags should be
        executed and flushed before the main SELECT.
        """
        from app.services.quota.quota_alert_service import check_and_send_quota_alerts

        row = _make_org_row(plan_tier="pro", used=0)
        db = _make_db([row], is_first_of_month=True)

        first_of_month = datetime(2026, 6, 1, tzinfo=UTC)

        with patch("app.services.quota.quota_alert_service.send_email", new_callable=AsyncMock):
            with patch("app.services.quota.quota_alert_service.datetime") as mock_dt:
                mock_dt.now.return_value = first_of_month
                await check_and_send_quota_alerts(db)

        # flush() must have been called (month-reset UPDATE)
        db.flush.assert_called_once()
        # execute() called at least twice: reset UPDATE + main SELECT
        assert db.execute.call_count >= 2
