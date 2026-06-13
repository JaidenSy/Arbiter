"""
Integration tests for the multi-org membership endpoints:

    POST /api/v1/org/switch        — switch the active organization
    POST /api/v1/org/leave         — leave the active organization
    POST /api/v1/auth/accept-invite — existing-account path (join as member)

Plus the membership-aware org-verified gate used by the proxy.

Uses the FastAPI test client with mocked DB (AsyncMock) and fake Redis,
following the conftest pattern — no live Postgres required.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_user(org_id: uuid.UUID, role: str = "member") -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    user.org_id = org_id
    user.role = role
    user.email = "dev@example.com"
    user.display_name = "Dev"
    user.is_active = True
    user.is_verified = True
    return user


def _make_membership(org_id: uuid.UUID, role: str) -> MagicMock:
    m = MagicMock()
    m.org_id = org_id
    m.role = role
    return m


def _make_db(scalar_side_effect: list) -> AsyncMock:
    db = AsyncMock()
    db.scalar = AsyncMock(side_effect=scalar_side_effect)
    exec_result = MagicMock()
    exec_result.scalar_one_or_none.return_value = None
    exec_result.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=exec_result)
    db.add = MagicMock()
    return db


async def _request(
    method: str,
    path: str,
    *,
    db: AsyncMock,
    fake_redis,
    user: MagicMock | None = None,
    optional_user: MagicMock | None = None,
    json: dict | None = None,
) -> object:
    """Issue a request with dependencies overridden."""
    from app.core.dependencies import (
        get_current_user,
        get_current_user_optional,
        get_db,
        get_redis,
    )
    from app.main import app

    async def _override_get_db():
        yield db

    async def _override_get_redis(request=None):
        return fake_redis

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis] = _override_get_redis
    if user is not None:

        async def _override_user():
            return user

        app.dependency_overrides[get_current_user] = _override_user

    async def _override_optional_user():
        return optional_user

    app.dependency_overrides[get_current_user_optional] = _override_optional_user

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, json=json)
    finally:
        for dep in (get_db, get_redis, get_current_user, get_current_user_optional):
            app.dependency_overrides.pop(dep, None)


# ── POST /org/switch ──────────────────────────────────────────────────────────


class TestSwitchOrg:
    async def test_switch_updates_projection_and_returns_tokens(self, fake_redis):
        org_a, org_b = uuid.uuid4(), uuid.uuid4()
        user = _make_user(org_a, role="owner")
        membership_b = _make_membership(org_b, "member")
        db = _make_db([membership_b])
        target_org = MagicMock(id=org_b, is_active=True)
        db.get = AsyncMock(return_value=target_org)

        resp = await _request(
            "POST",
            "/api/v1/org/switch",
            db=db,
            fake_redis=fake_redis,
            user=user,
            json={"org_id": str(org_b)},
        )

        assert resp.status_code == 200, resp.text
        assert user.org_id == org_b
        assert user.role == "member"
        body = resp.json()
        assert body["access_token"] and body["refresh_token"]

    async def test_switch_to_non_member_org_returns_403(self, fake_redis):
        org_a = uuid.uuid4()
        user = _make_user(org_a)
        db = _make_db([None])  # no membership

        resp = await _request(
            "POST",
            "/api/v1/org/switch",
            db=db,
            fake_redis=fake_redis,
            user=user,
            json={"org_id": str(uuid.uuid4())},
        )

        assert resp.status_code == 403, resp.text
        assert user.org_id == org_a  # projection untouched


# ── POST /org (create) ────────────────────────────────────────────────────────


class TestCreateOrg:
    async def test_fourth_org_in_a_day_is_rate_limited(self, fake_redis):
        """Org creation mirrors the registration limit — fresh free orgs reset quota."""
        from datetime import date

        user = _make_user(uuid.uuid4(), role="owner")
        db = _make_db([None])
        # Three orgs already created today (mocked flush can't mint real org
        # rows, so seed the counter instead of driving three real creates).
        await fake_redis.set(f"org_create:{user.id}:{date.today().isoformat()}", 3)

        resp = await _request(
            "POST",
            "/api/v1/org",
            db=db,
            fake_redis=fake_redis,
            user=user,
            json={"name": "Side Project 4"},
        )

        assert resp.status_code == 429, resp.text
        assert "tomorrow" in resp.json()["detail"].lower()
        db.add.assert_not_called()  # rejected before any DB writes


# ── POST /org/leave ───────────────────────────────────────────────────────────


class TestLeaveOrg:
    async def test_sole_owner_cannot_leave(self, fake_redis):
        org_a = uuid.uuid4()
        user = _make_user(org_a, role="owner")
        membership = _make_membership(org_a, "owner")
        db = _make_db([membership, 0])  # get_membership, count_other_owners

        resp = await _request("POST", "/api/v1/org/leave", db=db, fake_redis=fake_redis, user=user)

        assert resp.status_code == 400, resp.text
        assert "only owner" in resp.json()["detail"].lower()
        db.delete.assert_not_awaited()

    async def test_leave_repoints_to_remaining_membership(self, fake_redis):
        org_a, org_b = uuid.uuid4(), uuid.uuid4()
        user = _make_user(org_a, role="member")
        membership_a = _make_membership(org_a, "member")
        membership_b = _make_membership(org_b, "admin")
        owner_id = uuid.uuid4()
        # get_membership → a; _reassign owner_id → owner_id; repoint → b
        db = _make_db([membership_a, owner_id, membership_b])

        resp = await _request("POST", "/api/v1/org/leave", db=db, fake_redis=fake_redis, user=user)

        assert resp.status_code == 200, resp.text
        db.delete.assert_awaited_once_with(membership_a)
        assert user.org_id == org_b
        assert user.role == "admin"
        assert resp.json()["access_token"]


# ── POST /auth/accept-invite (existing account) ───────────────────────────────


def _make_invite(org_id: uuid.UUID, email: str) -> MagicMock:
    invite = MagicMock()
    invite.org_id = org_id
    invite.email = email
    invite.role = "member"
    invite.accepted_at = None
    invite.expires_at = datetime.now(tz=UTC) + timedelta(days=1)
    return invite


class TestAcceptInviteExistingAccount:
    async def test_unauthenticated_existing_email_returns_409_with_hint(self, fake_redis):
        org_id = uuid.uuid4()
        invite = _make_invite(org_id, "dev@example.com")
        existing = _make_user(uuid.uuid4())
        db = _make_db([invite, existing])  # invite preview, user-by-email

        resp = await _request(
            "POST",
            "/api/v1/auth/accept-invite",
            db=db,
            fake_redis=fake_redis,
            optional_user=None,
            json={"token": "tok_abc"},
        )

        # 409 (not 401): the global 401 handler genericizes details, which
        # would swallow the "log in and retry" hint the frontend needs.
        assert resp.status_code == 409, resp.text
        assert "already exists" in resp.json()["detail"]
        assert "Log in" in resp.json()["detail"]
        # The invite must NOT have been consumed by a failed attempt.
        db.execute.assert_not_awaited()

    async def test_authenticated_existing_user_joins_org(self, fake_redis):
        personal_org = uuid.uuid4()
        inviting_org = uuid.uuid4()
        user = _make_user(personal_org, role="owner")
        user.email = "dev@example.com"
        invite = _make_invite(inviting_org, "dev@example.com")

        # invite preview, user-by-email, existing-membership check (None)
        db = _make_db([invite, user, None])
        consume_result = MagicMock()
        consume_result.scalar_one_or_none.return_value = invite
        db.execute = AsyncMock(return_value=consume_result)

        resp = await _request(
            "POST",
            "/api/v1/auth/accept-invite",
            db=db,
            fake_redis=fake_redis,
            optional_user=user,
            json={"token": "tok_abc"},
        )

        assert resp.status_code == 201, resp.text
        # Membership row written and projection switched to the new org.
        from app.db.models.org_membership import OrgMembership

        added_memberships = [
            call.args[0]
            for call in db.add.call_args_list
            if isinstance(call.args[0], OrgMembership)
        ]
        assert len(added_memberships) == 1
        assert added_memberships[0].org_id == inviting_org
        assert added_memberships[0].role == "member"
        assert user.org_id == inviting_org
        assert user.role == "member"

    async def test_already_member_returns_409(self, fake_redis):
        inviting_org = uuid.uuid4()
        user = _make_user(inviting_org)
        user.email = "dev@example.com"
        invite = _make_invite(inviting_org, "dev@example.com")
        existing_membership = _make_membership(inviting_org, "member")

        db = _make_db([invite, user, existing_membership])

        resp = await _request(
            "POST",
            "/api/v1/auth/accept-invite",
            db=db,
            fake_redis=fake_redis,
            optional_user=user,
            json={"token": "tok_abc"},
        )

        assert resp.status_code == 409, resp.text
        db.execute.assert_not_awaited()  # invite not consumed


# ── Resource reassignment on leave / removal ─────────────────────────────────


class TestResourceReassignmentOnLeave:
    async def test_leave_deactivates_agents_before_reassignment(self, fake_redis):
        """
        When a member leaves, their agents must be deactivated BEFORE being
        reassigned to the org owner.  Both helpers filter on created_by_user_id,
        so reassigning first rewrites the column to the owner and the
        deactivation UPDATE matches zero rows — the departing member's API keys
        would keep working.  Counting the UPDATEs is not enough; we assert the
        order of the two statements.
        """
        org_id = uuid.uuid4()
        user = _make_user(org_id, role="member")
        membership = _make_membership(org_id, "member")
        owner_id = uuid.uuid4()

        db = _make_db([membership])
        db.scalar = AsyncMock(
            side_effect=[
                membership,  # get_membership
                owner_id,  # _reassign: select owner_id from org_memberships
                None,  # repoint: no remaining membership → create personal org
                None,  # create_org: slug uniqueness check
            ]
        )
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )
        db.get = AsyncMock(return_value=None)

        resp = await _request("POST", "/api/v1/org/leave", db=db, fake_redis=fake_redis, user=user)

        assert resp.status_code == 200, resp.text
        agent_updates = [
            str(call.args[0])
            for call in db.execute.await_args_list
            if "UPDATE agents" in str(call.args[0])
        ]
        deactivate_idx = next(
            (i for i, sql in enumerate(agent_updates) if "SET is_active" in sql), None
        )
        reassign_idx = next(
            (i for i, sql in enumerate(agent_updates) if "SET created_by_user_id" in sql), None
        )
        assert deactivate_idx is not None, "Deactivation UPDATE (SET is_active) never issued"
        assert reassign_idx is not None, "Reassignment UPDATE (SET created_by_user_id) never issued"
        assert deactivate_idx < reassign_idx, (
            "Agents must be deactivated before created_by_user_id is reassigned — "
            "reassigning first makes the deactivation a no-op and leaves the "
            "departing member's API keys live"
        )

    async def test_owner_cannot_leave_sole_owner(self, fake_redis):
        """Owner who is the only owner gets 400 before any DB mutation."""
        org_id = uuid.uuid4()
        user = _make_user(org_id, role="owner")
        membership = _make_membership(org_id, "owner")
        db = _make_db([membership, 0])  # get_membership → owner; count_other_owners → 0

        resp = await _request("POST", "/api/v1/org/leave", db=db, fake_redis=fake_redis, user=user)

        assert resp.status_code == 400, resp.text
        assert "only owner" in resp.json()["detail"].lower()
        db.delete.assert_not_awaited()
        db.execute.assert_not_awaited()


# ── GET /auth/invite-preview ──────────────────────────────────────────────────


class TestInvitePreview:
    async def test_returns_org_name_and_plan_tier(self, fake_redis):
        org_id = uuid.uuid4()
        invite = _make_invite(org_id, "newuser@example.com")
        invite.role = "member"

        org = MagicMock()
        org.id = org_id
        org.name = "Acme Corp"
        org.plan_tier = "pro"
        org.is_active = True

        db = _make_db([invite])
        db.get = AsyncMock(return_value=org)

        resp = await _request(
            "GET",
            "/api/v1/auth/invite-preview?token=tok_preview",
            db=db,
            fake_redis=fake_redis,
        )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["org_name"] == "Acme Corp"
        assert body["plan_tier"] == "pro"
        assert body["role"] == "member"
        assert body["email"] == "newuser@example.com"

    async def test_invalid_token_returns_400(self, fake_redis):
        db = _make_db([None])  # invite lookup → None

        resp = await _request(
            "GET",
            "/api/v1/auth/invite-preview?token=bad_token",
            db=db,
            fake_redis=fake_redis,
        )

        assert resp.status_code == 400, resp.text

    async def test_expired_invite_returns_400(self, fake_redis):
        org_id = uuid.uuid4()
        invite = _make_invite(org_id, "user@example.com")
        invite.expires_at = datetime.now(tz=UTC) - timedelta(days=1)  # expired

        db = _make_db([invite])

        resp = await _request(
            "GET",
            "/api/v1/auth/invite-preview?token=tok_expired",
            db=db,
            fake_redis=fake_redis,
        )

        assert resp.status_code == 400, resp.text


# ── Org-verified gate (membership-aware raw SQL) ──────────────────────────────


class TestEnsureOrgVerifiedMembershipAware:
    async def test_verified_member_passes(self):
        from app.core.dependencies import ensure_org_verified

        agent = MagicMock(org_id=uuid.uuid4())
        db = AsyncMock()
        result = MagicMock()
        result.scalar_one.return_value = True
        db.execute = AsyncMock(return_value=result)

        await ensure_org_verified(agent, db, redis=None)  # must not raise

    async def test_unverified_org_raises_403(self):
        from app.core.dependencies import ensure_org_verified

        agent = MagicMock(org_id=uuid.uuid4())
        db = AsyncMock()
        result = MagicMock()
        result.scalar_one.return_value = False
        db.execute = AsyncMock(return_value=result)

        with pytest.raises(HTTPException) as exc_info:
            await ensure_org_verified(agent, db, redis=None)
        assert exc_info.value.status_code == 403
