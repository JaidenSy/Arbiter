"""
Arbiter — API endpoints: Billing.

Exposes Stripe billing operations for the frontend and handles Stripe webhook
delivery for subscription lifecycle events.

Routes:
    GET    /billing/status    — return current plan, usage counts, and limits
    POST   /billing/checkout  — create a Stripe Checkout Session (upgrade to Pro)
    POST   /billing/portal    — create a Stripe Customer Portal session (manage subscription)
    POST   /billing/webhook   — receive and verify Stripe webhook events (no JWT auth)
"""

from __future__ import annotations

import logging

import stripe
import stripe.error
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_current_user, get_db
from app.db.models.agent import Agent
from app.db.models.mcp_server import MCPServer
from app.db.models.organization import Organization
from app.db.models.usage_event import UsageEvent
from app.db.models.user import User
from app.db.models.vault import VaultSecret
from app.services.billing.billing_service import BillingService
from app.services.plan.plan_limits import PLAN_LIMITS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])

billing_service = BillingService()


# ── Schemas ───────────────────────────────────────────────────────────────────


class BillingStatus(BaseModel):
    """Current billing state and resource usage for an org."""

    plan: str                         # "free" | "pro" | "enterprise"
    tool_calls_month: int
    tool_calls_limit: int | None      # None = unlimited (enterprise)
    agents_count: int
    agents_limit: int | None
    servers_count: int
    servers_limit: int | None
    vault_secrets_count: int
    vault_secrets_limit: int | None
    has_active_subscription: bool


class CheckoutRequest(BaseModel):
    """Request body for POST /billing/checkout."""

    price_id: str  # Stripe Price ID from frontend config


class PortalRequest(BaseModel):
    """Request body for POST /billing/portal."""

    return_url: str  # where Stripe portal sends user back — must be a valid https:// or http://localhost URL

    @field_validator("return_url")
    @classmethod
    def validate_return_url(cls, v: str) -> str:
        """Prevent open redirect: only allow http(s) URLs, no javascript: or data: schemes."""
        stripped = v.strip().lower()
        if not (stripped.startswith("https://") or stripped.startswith("http://localhost") or stripped.startswith("http://127.0.0.1")):
            raise ValueError("return_url must be a valid https:// URL")
        return v


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get(
    "/status",
    response_model=BillingStatus,
    summary="Get billing status and usage",
)
async def get_billing_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BillingStatus:
    """
    Return the org's current plan, resource counts, limits, and Stripe subscription ID.

    Counts active agents and MCP servers, all vault secrets, and tool calls made
    during the current calendar month.

    Args:
        db:           Injected async database session.
        current_user: Authenticated user (JWT).

    Returns:
        BillingStatus: Snapshot of the org's billing and usage state.
    """
    org = await db.get(Organization, current_user.org_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Org not found")

    # Monthly tool calls — sum UsageEvent rows for current month
    month_start = func.date_trunc("month", func.now())
    tool_calls_month: int = await db.scalar(
        select(func.coalesce(func.sum(UsageEvent.tool_calls), 0)).where(
            UsageEvent.org_id == org.id,
            UsageEvent.event_date >= month_start,
        )
    ) or 0

    # Resource counts — active agents / servers, all vault secrets
    agents_count: int = await db.scalar(
        select(func.count(Agent.id)).where(
            Agent.org_id == org.id,
            Agent.is_active.is_(True),
        )
    ) or 0

    servers_count: int = await db.scalar(
        select(func.count(MCPServer.id)).where(
            MCPServer.org_id == org.id,
            MCPServer.is_active.is_(True),
        )
    ) or 0

    vault_secrets_count: int = await db.scalar(
        select(func.count(VaultSecret.id)).where(
            VaultSecret.org_id == org.id,
        )
    ) or 0

    limits = PLAN_LIMITS[org.plan_tier]

    return BillingStatus(
        plan=org.plan_tier,
        tool_calls_month=tool_calls_month,
        tool_calls_limit=limits["max_tool_calls_mo"],
        agents_count=agents_count,
        agents_limit=limits["max_agents"],
        servers_count=servers_count,
        servers_limit=limits["max_mcp_servers"],
        vault_secrets_count=vault_secrets_count,
        vault_secrets_limit=limits["max_vault_secrets"],
        has_active_subscription=org.stripe_subscription_id is not None,
    )


@router.post(
    "/checkout",
    summary="Create a Stripe Checkout Session to upgrade to Pro",
)
async def create_checkout(
    body: CheckoutRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """
    Create a Stripe Checkout Session for upgrading to the Pro plan.

    Guards:
        - HTTP 400 if org is already on pro.
        - HTTP 400 if org is on enterprise (contact sales instead).
        - HTTP 503 if Stripe is not configured.

    Args:
        body:         Request body containing the Stripe price_id.
        db:           Injected async database session.
        current_user: Authenticated user (JWT).

    Returns:
        dict with ``url`` key pointing to the Stripe-hosted checkout page.
    """
    if not settings.stripe_secret_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Billing not configured",
        )

    org = await db.get(Organization, current_user.org_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Org not found")

    if org.plan_tier == "pro":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Already on pro plan",
        )
    if org.plan_tier == "enterprise":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Contact sales for enterprise billing",
        )

    success_url = f"{settings.frontend_url}/settings?tab=billing&status=success"
    cancel_url = f"{settings.frontend_url}/settings?tab=billing"

    try:
        url = await billing_service.create_checkout_session(
            org=org,
            price_id=body.price_id,
            success_url=success_url,
            cancel_url=cancel_url,
        )
    except stripe.error.StripeError as exc:
        logger.error("billing: Stripe error creating checkout session: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Billing provider error — please try again",
        ) from exc
    return {"url": url}


@router.post(
    "/portal",
    summary="Create a Stripe Customer Portal session",
)
async def create_portal(
    body: PortalRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """
    Create a Stripe Customer Portal session so the user can manage or cancel
    their subscription.

    Guards:
        - HTTP 400 if org has no stripe_customer_id (never purchased).
        - HTTP 503 if Stripe is not configured.

    Args:
        body:         Request body containing the return_url.
        db:           Injected async database session.
        current_user: Authenticated user (JWT).

    Returns:
        dict with ``url`` key pointing to the Stripe-hosted portal page.
    """
    if not settings.stripe_secret_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Billing not configured",
        )

    org = await db.get(Organization, current_user.org_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Org not found")

    if not org.stripe_customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active subscription",
        )

    try:
        url = await billing_service.create_portal_session(
            org=org,
            return_url=body.return_url,
        )
    except stripe.error.StripeError as exc:
        logger.error("billing: Stripe error creating portal session: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Billing provider error — please try again",
        ) from exc
    return {"url": url}


@router.post(
    "/webhook",
    status_code=status.HTTP_200_OK,
    summary="Stripe webhook receiver",
    include_in_schema=False,  # hide from public docs — unauthenticated endpoint
)
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    stripe_signature: str = Header(..., alias="stripe-signature"),
) -> dict[str, str]:
    """
    Receive and verify Stripe webhook events.

    IMPORTANT: This endpoint does NOT use JWT authentication.
    Authentication is performed via Stripe signature verification.

    The raw request body MUST be read with request.body() — do NOT use a
    Pydantic body parameter or call request.json(), as either would consume
    the stream and break Stripe's HMAC signature check.

    Args:
        request:          Raw FastAPI request (for body bytes).
        db:               Injected async database session.
        stripe_signature: Value of the stripe-signature header from Stripe.

    Returns:
        {"status": "ok"} on successful processing.

    Raises:
        HTTPException 400: On invalid or missing signature.
    """
    payload = await request.body()

    try:
        await billing_service.handle_webhook(
            payload=payload,
            sig_header=stripe_signature,
            db=db,
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Stripe signature",
        )

    return {"status": "ok"}
