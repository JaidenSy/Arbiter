"""
Integration tests for DELETE /api/v1/auth/me (GDPR account deletion).

Membership model: the account may belong to several orgs.  An org is deleted
with the account only when the user is an owner and no other active owner
remains; every other org survives untouched — including its Stripe
subscription and customer (plans attach to orgs, never to people).

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


def _make_mock_org(org_id: uuid.UUID, sub_id: str | None = "sub_live_123") -> MagicMock:
    org = MagicMock()
    org.id = org_id
    org.name = "Acme Corp"
    org.plan_tier = "pro"
    org.stripe_customer_id = "cus_live_123"
    org.stripe_subscription_id = sub_id
    return org


def _make_membership(org_id: uuid.UUID, role: str) -> MagicMock:
    m = MagicMock()
    m.org_id = org_id
    m.role = role
    return m


def _make_mock_db(
    memberships: list[MagicMock],
    orgs_by_id: dict[uuid.UUID, MagicMock],
    owner_counts: list[int],
) -> AsyncMock:
    """
    Mock AsyncSession for the delete_me flow.

    - db.execute → one shared result; .scalars().all() feeds list_memberships,
      every other execute is a bulk statement whose result is unused.
    - db.scalar  → sequential owner counts (one per owner-role membership).
    - db.get     → resolves (Organization, org_id) from orgs_by_id.
    """
    db = AsyncMock()
    exec_result = MagicMock()
    exec_result.scalars.return_value.all.return_value = memberships
    exec_result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=exec_result)
    db.scalar = AsyncMock(side_effect=owner_counts or [0])

    async def _get(_model, pk):
        return orgs_by_id.get(pk)

    db.get = AsyncMock(side_effect=_get)
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


def _gdpr_logs(db: AsyncMock) -> list:
    from app.db.models.gdpr_deletion_log import GdprDeletionLog

    return [
        call.args[0] for call in db.add.call_args_list if isinstance(call.args[0], GdprDeletionLog)
    ]


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestDeleteMeOrgBilling:
    async def test_member_delete_does_not_cancel_org_subscription(self, fake_redis):
        """A member deleting their account must not touch the surviving org's billing."""
        from app.core import config as config_module

        org_id = uuid.uuid4()
        user = _make_mock_user(org_id, role="member")
        org = _make_mock_org(org_id)
        db = _make_mock_db(
            memberships=[_make_membership(org_id, "member")],
            orgs_by_id={org_id: org},
            owner_counts=[],
        )

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

        logs = _gdpr_logs(db)
        assert len(logs) == 1
        assert logs[0].was_sole_owner is False
        assert logs[0].had_stripe_subscription is True

    async def test_co_owner_delete_does_not_cancel_org_subscription(self, fake_redis):
        """An owner deleting their account while another owner remains keeps billing intact."""
        from app.core import config as config_module

        org_id = uuid.uuid4()
        user = _make_mock_user(org_id, role="owner")
        org = _make_mock_org(org_id)
        db = _make_mock_db(
            memberships=[_make_membership(org_id, "owner")],
            orgs_by_id={org_id: org},
            owner_counts=[1],
        )

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

    async def test_sole_owner_delete_cancels_subscription_and_deletes_org(self, fake_redis):
        """The sole owner deleting their account cancels billing and removes the org."""
        from app.core import config as config_module

        org_id = uuid.uuid4()
        user = _make_mock_user(org_id, role="owner")
        org = _make_mock_org(org_id)
        db = _make_mock_db(
            memberships=[_make_membership(org_id, "owner")],
            orgs_by_id={org_id: org},
            owner_counts=[0],
        )

        with (
            patch.object(config_module.settings, "stripe_secret_key", "sk_test_fake"),
            patch("stripe.Subscription.cancel") as mock_cancel,
        ):
            resp = await _call_delete_me(user, db, fake_redis)

        assert resp.status_code == 204, f"Expected 204, got {resp.status_code}: {resp.text}"
        mock_cancel.assert_called_once_with("sub_live_123")
        assert org.plan_tier == "free"
        assert org.stripe_subscription_id is None
        assert org.stripe_customer_id is None
        db.delete.assert_awaited_once_with(org)

        # had_stripe_subscription must reflect the state BEFORE cancellation.
        logs = _gdpr_logs(db)
        assert len(logs) == 1
        assert logs[0].was_sole_owner is True
        assert logs[0].had_stripe_subscription is True

    async def test_multi_org_deletes_only_solely_owned_org(self, fake_redis):
        """
        Sole-owner personal org dies with the account; the team org where the
        user is just a member survives with its subscription untouched.
        """
        from app.core import config as config_module

        personal_id = uuid.uuid4()
        team_id = uuid.uuid4()
        personal = _make_mock_org(personal_id, sub_id="sub_personal")
        team = _make_mock_org(team_id, sub_id="sub_team")
        user = _make_mock_user(personal_id, role="owner")
        db = _make_mock_db(
            memberships=[
                _make_membership(personal_id, "owner"),
                _make_membership(team_id, "member"),
            ],
            orgs_by_id={personal_id: personal, team_id: team},
            owner_counts=[0],  # only the owner membership triggers a count
        )

        with (
            patch.object(config_module.settings, "stripe_secret_key", "sk_test_fake"),
            patch("stripe.Subscription.cancel") as mock_cancel,
        ):
            resp = await _call_delete_me(user, db, fake_redis)

        assert resp.status_code == 204, f"Expected 204, got {resp.status_code}: {resp.text}"
        mock_cancel.assert_called_once_with("sub_personal")
        assert personal.plan_tier == "free"
        db.delete.assert_awaited_once_with(personal)

        assert team.plan_tier == "pro"
        assert team.stripe_subscription_id == "sub_team"
        assert team.stripe_customer_id == "cus_live_123"

        logs = _gdpr_logs(db)
        assert {(log.was_sole_owner, log.org_id) for log in logs} == {
            (True, personal_id),
            (False, team_id),
        }
