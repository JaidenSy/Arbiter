"""
Integration tests for the billing endpoints:
    GET    /api/v1/billing/status
    POST   /api/v1/billing/checkout
    POST   /api/v1/billing/portal
    POST   /api/v1/billing/webhook

Uses the FastAPI test client with mocked DB (AsyncMock) and fake Redis.
Stripe SDK calls are mocked via unittest.mock.patch — no real API keys required.

Coverage:
    - GET  /billing/status returns correct plan, counts, limits for a free org
    - POST /billing/checkout returns 503 when stripe_secret_key is empty (not configured)
    - POST /billing/checkout returns 400 when org is already on pro plan
    - POST /billing/portal  returns 400 when org has no stripe_customer_id
    - POST /billing/webhook returns 400 on invalid Stripe signature
    - POST /billing/webhook returns 200 and processes checkout.session.completed
    - POST /billing/webhook idempotency: duplicate event does not re-write org
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_mock_user(org_id: uuid.UUID) -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    user.org_id = org_id
    user.is_active = True
    user.email = "test@example.com"
    return user


def _make_mock_org(
    plan_tier: str = "free",
    org_id: uuid.UUID | None = None,
    stripe_customer_id: str | None = None,
    stripe_subscription_id: str | None = None,
) -> MagicMock:
    org = MagicMock()
    org.id = org_id or uuid.uuid4()
    org.plan_tier = plan_tier
    org.stripe_customer_id = stripe_customer_id
    org.stripe_subscription_id = stripe_subscription_id
    return org


def _build_db_for_billing_status(
    org: MagicMock,
    tool_calls_month: int = 0,
    agents_count: int = 0,
    servers_count: int = 0,
    vault_secrets_count: int = 0,
) -> AsyncMock:
    """
    Build a mock DB that returns the right scalar values for the billing status
    endpoint's four sequential scalar() queries.

    Query order in billing.py get_billing_status:
        1. tool_calls_month  (coalesce sum)
        2. agents_count
        3. servers_count
        4. vault_secrets_count
    """
    db = AsyncMock()
    scalars = [tool_calls_month, agents_count, servers_count, vault_secrets_count]
    call_index = [0]  # mutable container so inner func can increment

    async def mock_scalar(stmt):
        idx = call_index[0]
        call_index[0] += 1
        if idx < len(scalars):
            return scalars[idx]
        return 0

    db.scalar = mock_scalar

    # db.get(Organization, org_id) — used in all endpoints
    async def mock_get(model_class, pk):
        return org

    db.get = mock_get
    return db


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def billing_client(fake_redis) -> AsyncGenerator:
    """
    HTTPX test client with get_current_user overridden to return a mock user.
    The org fixture is configured per-test via separate DB mock injection.
    Yields (client, mock_user, org_id).
    """
    from app.main import app
    from app.core.dependencies import get_db, get_redis, get_current_user

    org_id = uuid.uuid4()
    mock_user = _make_mock_user(org_id=org_id)

    async def override_get_redis(request=None):
        return fake_redis

    async def override_get_current_user():
        return mock_user

    app.dependency_overrides[get_redis] = override_get_redis
    app.dependency_overrides[get_current_user] = override_get_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, mock_user, org_id

    app.dependency_overrides.clear()


# ── GET /billing/status tests ─────────────────────────────────────────────────

class TestBillingStatus:
    @pytest.mark.asyncio
    async def test_returns_free_plan_defaults(self, billing_client, fake_redis):
        """
        A free org with no resources should return plan=free, all counts=0,
        and limits matching the free tier PLAN_LIMITS constants.
        """
        from app.main import app
        from app.core.dependencies import get_db
        from app.services.plan.plan_limits import PLAN_LIMITS

        client, mock_user, org_id = billing_client
        org = _make_mock_org(plan_tier="free", org_id=org_id)
        db = _build_db_for_billing_status(org=org)

        async def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db
        try:
            resp = await client.get("/api/v1/billing/status")
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()

        assert data["plan"] == "free"
        assert data["tool_calls_month"] == 0
        assert data["tool_calls_limit"] == PLAN_LIMITS["free"]["max_tool_calls_mo"]
        assert data["agents_count"] == 0
        assert data["agents_limit"] == PLAN_LIMITS["free"]["max_agents"]
        assert data["servers_count"] == 0
        assert data["servers_limit"] == PLAN_LIMITS["free"]["max_mcp_servers"]
        assert data["vault_secrets_count"] == 0
        assert data["vault_secrets_limit"] == PLAN_LIMITS["free"]["max_vault_secrets"]
        assert data["stripe_subscription_id"] is None

    @pytest.mark.asyncio
    async def test_returns_correct_usage_counts(self, billing_client):
        """Org with 2 agents, 3 servers, 5 vault secrets, 200 tool calls."""
        from app.main import app
        from app.core.dependencies import get_db

        client, mock_user, org_id = billing_client
        org = _make_mock_org(plan_tier="free", org_id=org_id)
        db = _build_db_for_billing_status(
            org=org,
            tool_calls_month=200,
            agents_count=2,
            servers_count=3,
            vault_secrets_count=5,
        )

        async def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db
        try:
            resp = await client.get("/api/v1/billing/status")
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200
        data = resp.json()
        assert data["tool_calls_month"] == 200
        assert data["agents_count"] == 2
        assert data["servers_count"] == 3
        assert data["vault_secrets_count"] == 5

    @pytest.mark.asyncio
    async def test_enterprise_limits_are_null(self, billing_client):
        """Enterprise org should return None for all limit fields."""
        from app.main import app
        from app.core.dependencies import get_db

        client, mock_user, org_id = billing_client
        org = _make_mock_org(plan_tier="enterprise", org_id=org_id)
        db = _build_db_for_billing_status(org=org)

        async def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db
        try:
            resp = await client.get("/api/v1/billing/status")
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200
        data = resp.json()
        assert data["plan"] == "enterprise"
        assert data["tool_calls_limit"] is None
        assert data["agents_limit"] is None
        assert data["servers_limit"] is None
        assert data["vault_secrets_limit"] is None

    @pytest.mark.asyncio
    async def test_includes_stripe_subscription_id_when_set(self, billing_client):
        """Org with an active subscription should return its stripe_subscription_id."""
        from app.main import app
        from app.core.dependencies import get_db

        client, mock_user, org_id = billing_client
        org = _make_mock_org(
            plan_tier="pro",
            org_id=org_id,
            stripe_subscription_id="sub_abc123",
        )
        db = _build_db_for_billing_status(org=org)

        async def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db
        try:
            resp = await client.get("/api/v1/billing/status")
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200
        data = resp.json()
        assert data["stripe_subscription_id"] == "sub_abc123"

    @pytest.mark.asyncio
    async def test_requires_auth(self, test_client):
        """GET /billing/status without Authorization header → 401"""
        resp = await test_client.get("/api/v1/billing/status")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"


# ── POST /billing/checkout tests ──────────────────────────────────────────────

class TestBillingCheckout:
    @pytest.mark.asyncio
    async def test_returns_503_when_stripe_not_configured(self, billing_client):
        """
        When settings.stripe_secret_key is empty, the endpoint must return 503
        before even touching the DB or Stripe SDK.
        """
        from app.main import app
        from app.core.dependencies import get_db
        from app.core import config as config_module

        client, mock_user, org_id = billing_client
        org = _make_mock_org(plan_tier="free", org_id=org_id)
        db = AsyncMock()
        db.get = AsyncMock(return_value=org)

        async def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db
        try:
            with patch.object(config_module.settings, "stripe_secret_key", ""):
                resp = await client.post(
                    "/api/v1/billing/checkout",
                    json={"price_id": "price_test123"},
                )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 503, f"Expected 503, got {resp.status_code}: {resp.text}"
        assert "not configured" in resp.json().get("detail", "").lower()

    @pytest.mark.asyncio
    async def test_returns_400_when_already_on_pro(self, billing_client):
        """
        Org already on pro plan → 400 Bad Request.
        """
        from app.main import app
        from app.core.dependencies import get_db
        from app.core import config as config_module

        client, mock_user, org_id = billing_client
        org = _make_mock_org(plan_tier="pro", org_id=org_id)
        db = AsyncMock()
        db.get = AsyncMock(return_value=org)

        async def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db
        try:
            with patch.object(config_module.settings, "stripe_secret_key", "sk_test_fake"):
                resp = await client.post(
                    "/api/v1/billing/checkout",
                    json={"price_id": "price_test123"},
                )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        assert "pro" in resp.json().get("detail", "").lower()

    @pytest.mark.asyncio
    async def test_returns_400_when_on_enterprise(self, billing_client):
        """Enterprise orgs should be told to contact sales → 400."""
        from app.main import app
        from app.core.dependencies import get_db
        from app.core import config as config_module

        client, mock_user, org_id = billing_client
        org = _make_mock_org(plan_tier="enterprise", org_id=org_id)
        db = AsyncMock()
        db.get = AsyncMock(return_value=org)

        async def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db
        try:
            with patch.object(config_module.settings, "stripe_secret_key", "sk_test_fake"):
                resp = await client.post(
                    "/api/v1/billing/checkout",
                    json={"price_id": "price_test123"},
                )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"

    @pytest.mark.asyncio
    async def test_returns_checkout_url_for_free_org(self, billing_client):
        """
        Free org with Stripe configured → BillingService creates checkout session,
        endpoint returns {"url": "..."}.
        Stripe SDK is mocked — no real API key needed.
        """
        from app.main import app
        from app.core.dependencies import get_db
        from app.core import config as config_module

        client, mock_user, org_id = billing_client
        org = _make_mock_org(plan_tier="free", org_id=org_id)
        db = AsyncMock()
        db.get = AsyncMock(return_value=org)

        fake_session = MagicMock()
        fake_session.url = "https://checkout.stripe.com/pay/cs_test_fake"

        async def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db
        try:
            with patch.object(config_module.settings, "stripe_secret_key", "sk_test_fake"), \
                 patch("stripe.checkout.Session.create", return_value=fake_session):
                resp = await client.post(
                    "/api/v1/billing/checkout",
                    json={"price_id": "price_pro_monthly"},
                )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "url" in data
        assert data["url"] == "https://checkout.stripe.com/pay/cs_test_fake"


# ── POST /billing/portal tests ────────────────────────────────────────────────

class TestBillingPortal:
    @pytest.mark.asyncio
    async def test_returns_400_when_no_stripe_customer_id(self, billing_client):
        """
        Org has no stripe_customer_id (never subscribed) → 400 Bad Request.
        """
        from app.main import app
        from app.core.dependencies import get_db
        from app.core import config as config_module

        client, mock_user, org_id = billing_client
        org = _make_mock_org(plan_tier="pro", org_id=org_id, stripe_customer_id=None)
        db = AsyncMock()
        db.get = AsyncMock(return_value=org)

        async def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db
        try:
            with patch.object(config_module.settings, "stripe_secret_key", "sk_test_fake"):
                resp = await client.post(
                    "/api/v1/billing/portal",
                    json={"return_url": "https://app.example.com/settings"},
                )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        assert "subscription" in resp.json().get("detail", "").lower()

    @pytest.mark.asyncio
    async def test_returns_503_when_stripe_not_configured(self, billing_client):
        """Portal also returns 503 when Stripe is not configured."""
        from app.main import app
        from app.core.dependencies import get_db
        from app.core import config as config_module

        client, mock_user, org_id = billing_client
        org = _make_mock_org(plan_tier="pro", org_id=org_id, stripe_customer_id="cus_abc")
        db = AsyncMock()
        db.get = AsyncMock(return_value=org)

        async def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db
        try:
            with patch.object(config_module.settings, "stripe_secret_key", ""):
                resp = await client.post(
                    "/api/v1/billing/portal",
                    json={"return_url": "https://app.example.com/settings"},
                )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 503, f"Expected 503, got {resp.status_code}: {resp.text}"

    @pytest.mark.asyncio
    async def test_returns_portal_url_when_customer_exists(self, billing_client):
        """
        Org with stripe_customer_id → BillingService creates portal session,
        endpoint returns {"url": "..."}.
        """
        from app.main import app
        from app.core.dependencies import get_db
        from app.core import config as config_module

        client, mock_user, org_id = billing_client
        org = _make_mock_org(
            plan_tier="pro",
            org_id=org_id,
            stripe_customer_id="cus_abc123",
        )
        db = AsyncMock()
        db.get = AsyncMock(return_value=org)

        fake_session = MagicMock()
        fake_session.url = "https://billing.stripe.com/session/fake"

        async def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db
        try:
            with patch.object(config_module.settings, "stripe_secret_key", "sk_test_fake"), \
                 patch("stripe.billing_portal.Session.create", return_value=fake_session):
                resp = await client.post(
                    "/api/v1/billing/portal",
                    json={"return_url": "https://app.example.com/settings"},
                )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "url" in data
        assert data["url"] == "https://billing.stripe.com/session/fake"


# ── POST /billing/webhook tests ───────────────────────────────────────────────

class TestBillingWebhook:
    @pytest.mark.asyncio
    async def test_returns_400_on_invalid_signature(self, test_client):
        """
        Webhook with bad stripe-signature header must return 400.
        stripe.Webhook.construct_event is mocked to raise SignatureVerificationError.
        """
        import stripe.error

        with patch(
            "stripe.Webhook.construct_event",
            side_effect=stripe.error.SignatureVerificationError(
                "Signature mismatch", sig_header="t=123,v1=bad"
            ),
        ):
            resp = await test_client.post(
                "/api/v1/billing/webhook",
                content=b'{"type":"test"}',
                headers={
                    "stripe-signature": "t=123,v1=badsig",
                    "Content-Type": "application/json",
                },
            )

        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        assert "signature" in resp.json().get("detail", "").lower()

    @pytest.mark.asyncio
    async def test_returns_200_on_valid_signature_noop_event(self, fake_redis):
        """
        A valid signature with an unhandled event type (e.g., payment_intent.created)
        should return 200 {"status": "ok"} silently.
        """
        from httpx import AsyncClient, ASGITransport
        from app.main import app
        from app.core.dependencies import get_db, get_redis

        org_id = str(uuid.uuid4())

        # Build a minimal Stripe event dict for a no-op type
        fake_event = {
            "type": "payment_intent.created",
            "data": {"object": {"metadata": {"org_id": org_id}}},
        }

        db = AsyncMock()
        db.get = AsyncMock(return_value=None)

        async def override_get_db():
            yield db

        async def override_get_redis(request=None):
            return fake_redis

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_redis] = override_get_redis

        try:
            with patch("stripe.Webhook.construct_event", return_value=fake_event):
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    resp = await client.post(
                        "/api/v1/billing/webhook",
                        content=b'{}',
                        headers={
                            "stripe-signature": "t=123,v1=fakesig",
                            "Content-Type": "application/json",
                        },
                    )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        assert resp.json() == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_checkout_completed_upgrades_org_to_pro(self, fake_redis):
        """
        checkout.session.completed event with a valid org_id in metadata should:
        - Load the org from DB
        - Set plan_tier = "pro"
        - Set stripe_customer_id and stripe_subscription_id
        - Commit the session
        """
        from httpx import AsyncClient, ASGITransport
        from app.main import app
        from app.core.dependencies import get_db, get_redis

        org_id = str(uuid.uuid4())
        org = _make_mock_org(plan_tier="free", org_id=uuid.UUID(org_id))
        org.stripe_subscription_id = None  # not yet set → idempotency guard passes

        fake_event = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "metadata": {"org_id": org_id},
                    "customer": "cus_newcustomer",
                    "subscription": "sub_newsubscription",
                }
            },
        }

        db = AsyncMock()
        db.get = AsyncMock(return_value=org)
        db.commit = AsyncMock()

        async def override_get_db():
            yield db

        async def override_get_redis(request=None):
            return fake_redis

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_redis] = override_get_redis

        try:
            with patch("stripe.Webhook.construct_event", return_value=fake_event):
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    resp = await client.post(
                        "/api/v1/billing/webhook",
                        content=b'{}',
                        headers={
                            "stripe-signature": "t=123,v1=fakesig",
                            "Content-Type": "application/json",
                        },
                    )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        assert org.plan_tier == "pro"
        assert org.stripe_customer_id == "cus_newcustomer"
        assert org.stripe_subscription_id == "sub_newsubscription"
        db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_checkout_completed_idempotency_guard(self, fake_redis):
        """
        Sending the same checkout.session.completed event twice must only commit once.
        On the second call, the org.stripe_subscription_id already equals the event's
        subscription ID — the handler should skip without committing.
        """
        from httpx import AsyncClient, ASGITransport
        from app.main import app
        from app.core.dependencies import get_db, get_redis

        org_id = str(uuid.uuid4())
        sub_id = "sub_alreadyset"
        org = _make_mock_org(plan_tier="pro", org_id=uuid.UUID(org_id))
        org.stripe_subscription_id = sub_id  # already set = idempotency guard fires

        fake_event = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "metadata": {"org_id": org_id},
                    "customer": "cus_existing",
                    "subscription": sub_id,
                }
            },
        }

        db = AsyncMock()
        db.get = AsyncMock(return_value=org)
        db.commit = AsyncMock()

        async def override_get_db():
            yield db

        async def override_get_redis(request=None):
            return fake_redis

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_redis] = override_get_redis

        try:
            with patch("stripe.Webhook.construct_event", return_value=fake_event):
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    resp = await client.post(
                        "/api/v1/billing/webhook",
                        content=b'{}',
                        headers={
                            "stripe-signature": "t=123,v1=fakesig",
                            "Content-Type": "application/json",
                        },
                    )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        # Idempotency guard: commit must NOT have been called
        db.commit.assert_not_called()
