"""
Integration tests for DELETE /api/v1/auth/me (GDPR account deletion).

Covers the org-billing regression: the org's Stripe subscription belongs to
the org, not the deleting user.  It must only be cancelled when the org
itself is deleted (sole-owner case).  A member or co-owner deleting their own
account must leave the surviving org's plan tier, subscription ID, and Stripe
customer ID untouched.

Uses the FastAPI test client with mocked DB (AsyncMock) and fake Redis.
Stripe SDK calls are mocked via unittest.mock.patch — no real API keys required.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import ASGITransport, AsyncClient

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_mock_user(org_id: uuid.UUID, role: str = "member") -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    user.org_id = org_id
    user.email = "leaver@example.com"
    user.display_name = "Leaver"
    user.role = role
    user.is_active = True
    user.is_verified = True
    return user


def _make_mock_org(org_id: uuid.UUID) -> MagicMock:
    org = MagicMock()
    org.id = org_id
    org.name = "Acme Corp"
    org.plan_tier = "pro"
    org.stripe_customer_id = "cus_live_123"
    org.stripe_subscription_id = "sub_live_123"
    return org


def _make_mock_db(org: MagicMock, other_owner_count: int) -> AsyncMock:
    """
    Mock AsyncSession for the delete_me flow.

    delete_me issues exactly one db.scalar() call (the count of other active
    owners); every db.execute() is a bulk UPDATE/DELETE whose result is unused.
    """
    db = AsyncMock()
    db.get = AsyncMock(return_value=org)
    db.scalar = AsyncMock(return_value=other_owner_count)
    exec_result = MagicMock()
    exec_result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=exec_result)
    db.add = MagicMock()
    return db


async def _call_delete_me(user: MagicMock, db: AsyncMock, fake_redis) -> object:
    """Issue DELETE /api/v1/auth/me with all dependencies overridden."""
    from app.core.dependencies import get_current_user, get_db, get_redis
    from app.main import app

    async def _override_get_db():
        yield db

    async def _override_get_redis(request=None):
        return fake_redis

    async def _override_get_current_user():
        return user

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis] = _override_get_redis
    app.dependency_overrides[get_current_user] = _override_get_current_user
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.delete("/api/v1/auth/me")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_redis, None)
        app.dependency_overrides.pop(get_current_user, None)


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestDeleteMeOrgBilling:
    async def test_member_delete_does_not_cancel_org_subscription(self, fake_redis):
        """A member deleting their account must not touch the org's billing."""
        from app.core import config as config_module

        org_id = uuid.uuid4()
        user = _make_mock_user(org_id, role="member")
        org = _make_mock_org(org_id)
        db = _make_mock_db(org, other_owner_count=1)

        with (
            patch.object(config_module.settings, "stripe_secret_key", "sk_test_fake"),
            patch("stripe.Subscription.cancel") as mock_cancel,
        ):
            resp = await _call_delete_me(user, db, fake_redis)

        assert resp.status_code == 204, f"Expected 204, got {resp.status_code}: {resp.text}"
        mock_cancel.assert_not_called()
        assert org.plan_tier == "pro"
        assert org.stripe_subscription_id == "sub_live_123"
        assert org.stripe_customer_id == "cus_live_123"
        db.delete.assert_not_awaited()

    async def test_co_owner_delete_does_not_cancel_org_subscription(self, fake_redis):
        """An owner deleting their account while another owner remains keeps billing intact."""
        from app.core import config as config_module

        org_id = uuid.uuid4()
        user = _make_mock_user(org_id, role="owner")
        org = _make_mock_org(org_id)
        db = _make_mock_db(org, other_owner_count=1)

        with (
            patch.object(config_module.settings, "stripe_secret_key", "sk_test_fake"),
            patch("stripe.Subscription.cancel") as mock_cancel,
        ):
            resp = await _call_delete_me(user, db, fake_redis)

        assert resp.status_code == 204, f"Expected 204, got {resp.status_code}: {resp.text}"
        mock_cancel.assert_not_called()
        assert org.plan_tier == "pro"
        assert org.stripe_subscription_id == "sub_live_123"
        assert org.stripe_customer_id == "cus_live_123"
        db.delete.assert_not_awaited()

    async def test_surviving_org_gdpr_log_records_non_sole_owner(self, fake_redis):
        """The GDPR audit row for a surviving org must record was_sole_owner=False."""
        from app.core import config as config_module
        from app.db.models.gdpr_deletion_log import GdprDeletionLog

        org_id = uuid.uuid4()
        user = _make_mock_user(org_id, role="member")
        org = _make_mock_org(org_id)
        db = _make_mock_db(org, other_owner_count=2)

        with (
            patch.object(config_module.settings, "stripe_secret_key", "sk_test_fake"),
            patch("stripe.Subscription.cancel"),
        ):
            resp = await _call_delete_me(user, db, fake_redis)

        assert resp.status_code == 204
        gdpr_rows = [
            call.args[0]
            for call in db.add.call_args_list
            if isinstance(call.args[0], GdprDeletionLog)
        ]
        assert len(gdpr_rows) == 1
        assert gdpr_rows[0].was_sole_owner is False
        assert gdpr_rows[0].had_stripe_subscription is True

    async def test_sole_owner_delete_cancels_subscription_and_deletes_org(self, fake_redis):
        """The sole owner deleting their account cancels billing and removes the org."""
        from app.core import config as config_module

        org_id = uuid.uuid4()
        user = _make_mock_user(org_id, role="owner")
        org = _make_mock_org(org_id)
        db = _make_mock_db(org, other_owner_count=0)

        with (
            patch.object(config_module.settings, "stripe_secret_key", "sk_test_fake"),
            patch("stripe.Subscription.cancel") as mock_cancel,
        ):
            resp = await _call_delete_me(user, db, fake_redis)

        assert resp.status_code == 204, f"Expected 204, got {resp.status_code}: {resp.text}"
        mock_cancel.assert_called_once_with("sub_live_123")
        assert org.plan_tier == "free"
        assert org.stripe_subscription_id is None
        db.delete.assert_awaited_once_with(org)
