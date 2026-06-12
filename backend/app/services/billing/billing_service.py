"""
Arbiter — Stripe billing service.

Wraps Stripe SDK calls for checkout, customer portal, and webhook handling.
All Stripe calls are synchronous (stripe-python is not async-native) — wrapped
in asyncio.to_thread() to avoid blocking the event loop.

Webhook handler verifies signature first, then dispatches on event type.
Only these event types are acted upon:
    - checkout.session.completed     → set stripe IDs, upgrade to "pro"
    - customer.subscription.updated  → sync plan_tier from subscription status
    - customer.subscription.deleted  → downgrade to "free", clear stripe_subscription_id
    - invoice.payment_failed         → email org owner with portal link to update payment method
"""

from __future__ import annotations

import asyncio
import logging

import stripe
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.org_membership import OrgMembership
from app.db.models.organization import Organization
from app.db.models.user import User
from app.services.email.email_service import send_payment_failed

logger = logging.getLogger(__name__)


class BillingService:
    """Stripe billing operations for checkout, portal, and webhook handling."""

    def __init__(self) -> None:
        stripe.api_key = settings.stripe_secret_key

    # ── Checkout ──────────────────────────────────────────────────────────────

    async def create_checkout_session(
        self,
        org: Organization,
        price_id: str,
        success_url: str,
        cancel_url: str,
    ) -> str:
        """
        Create a Stripe Checkout Session for upgrading to Pro.

        If org already has a stripe_customer_id, pass it as customer= so
        Stripe attaches the subscription to the existing customer record.
        Otherwise let Stripe create a new customer (it returns customer ID
        in the webhook — we store it then).

        Args:
            org:         The organization initiating the checkout.
            price_id:    Stripe Price ID for the Pro plan.
            success_url: URL to redirect to on successful payment.
            cancel_url:  URL to redirect to on cancelled payment.

        Returns:
            The hosted checkout URL.
        """
        kwargs: dict = {
            "mode": "subscription",
            "line_items": [{"price": price_id, "quantity": 1}],
            "success_url": success_url,
            "cancel_url": cancel_url,
            "metadata": {"org_id": str(org.id)},
            "subscription_data": {"metadata": {"org_id": str(org.id)}},
            "automatic_tax": {"enabled": True},
        }
        if org.stripe_customer_id:
            kwargs["customer"] = org.stripe_customer_id

        session = await asyncio.to_thread(stripe.checkout.Session.create, **kwargs)
        return session.url

    # ── Portal ────────────────────────────────────────────────────────────────

    async def create_portal_session(
        self,
        org: Organization,
        return_url: str,
    ) -> str:
        """
        Create a Stripe Customer Portal session.

        Requires org.stripe_customer_id to be set — caller must guard this.

        Args:
            org:        The organization requesting portal access.
            return_url: URL to redirect to when the user exits the portal.

        Returns:
            The portal URL.
        """
        session = await asyncio.to_thread(
            stripe.billing_portal.Session.create,
            customer=org.stripe_customer_id,
            return_url=return_url,
        )
        return session.url

    # ── Webhook ───────────────────────────────────────────────────────────────

    async def handle_webhook(
        self,
        payload: bytes,
        sig_header: str,
        db: AsyncSession,
    ) -> None:
        """
        Verify Stripe webhook signature and dispatch on event type.

        Raises stripe.error.SignatureVerificationError on bad signature —
        the endpoint converts this to HTTP 400.

        Args:
            payload:    Raw request body bytes — must NOT be parsed before calling.
            sig_header: Value of the stripe-signature header.
            db:         Async database session for persisting org state changes.

        Event handling:
            checkout.session.completed:
                - Extract org_id from metadata
                - Idempotency guard: skip if stripe_subscription_id already matches
                - Set org.stripe_customer_id, org.stripe_subscription_id
                - Set org.plan_tier = "pro"
                - Commit

            customer.subscription.updated:
                - Lookup org by stripe_customer_id
                - If subscription.status == "active" → plan_tier = "pro"
                - If subscription.status in ("past_due", "unpaid", "canceled") → plan_tier = "free"
                - Commit

            customer.subscription.deleted:
                - Lookup org by stripe_customer_id
                - Set plan_tier = "free", stripe_subscription_id = None
                - Commit

            invoice.payment_failed:
                - Lookup org by stripe_customer_id
                - Query org owner (role == "owner")
                - Generate billing portal URL
                - Email owner with link to update payment method

        All other event types: no-op (return silently).
        """
        event = await asyncio.to_thread(
            stripe.Webhook.construct_event,
            payload,
            sig_header,
            settings.stripe_webhook_secret,
        )

        await self.dispatch_event(event=event, db=db)

    async def dispatch_event(self, event: dict, db: AsyncSession) -> None:
        """
        Dispatch a pre-parsed Stripe event dict to the appropriate handler.

        Separated from handle_webhook so the endpoint can verify the signature
        and perform idempotency checks before dispatching.
        """
        event_type: str = event["type"]
        data: dict = event["data"]["object"]

        if event_type == "checkout.session.completed":
            await self._on_checkout_completed(data, db)
        elif event_type == "customer.subscription.updated":
            await self._on_subscription_updated(data, db)
        elif event_type == "customer.subscription.deleted":
            await self._on_subscription_deleted(data, db)
        elif event_type == "invoice.payment_failed":
            await self._on_payment_failed(data, db)
        # All other event types: no-op

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _on_checkout_completed(self, session: dict, db: AsyncSession) -> None:
        """Handle checkout.session.completed — upgrade org to pro."""
        org_id: str | None = (session.get("metadata") or {}).get("org_id")
        if not org_id:
            logger.warning("billing: checkout.session.completed missing org_id in metadata")
            return

        customer_id: str | None = session.get("customer")
        subscription_id: str | None = session.get("subscription")

        org = await db.get(Organization, org_id)
        if org is None:
            logger.warning("billing: org %s not found for checkout.session.completed", org_id)
            return

        # Idempotency guard — skip if subscription already matches
        if org.stripe_subscription_id == subscription_id and subscription_id is not None:
            return

        org.stripe_customer_id = customer_id
        org.stripe_subscription_id = subscription_id
        org.plan_tier = "pro"
        await db.commit()
        logger.info("billing: org %s upgraded to pro (sub=%s)", org_id, subscription_id)

    async def _on_subscription_updated(self, subscription: dict, db: AsyncSession) -> None:
        """Handle customer.subscription.updated — sync plan_tier from status."""
        org_id: str | None = (subscription.get("metadata") or {}).get("org_id")
        status: str = subscription.get("status", "")

        if not org_id:
            logger.warning("billing: customer.subscription.updated missing org_id in metadata")
            return

        org = await db.get(Organization, org_id)
        if org is None:
            logger.warning("billing: org %s not found for subscription.updated", org_id)
            return

        if status == "active":
            org.plan_tier = "pro"
        elif status in ("past_due", "unpaid", "canceled"):
            org.plan_tier = "free"

        await db.commit()
        logger.info("billing: org %s subscription.updated status=%s", org_id, status)

    async def _on_subscription_deleted(self, subscription: dict, db: AsyncSession) -> None:
        """Handle customer.subscription.deleted — downgrade org to free."""
        org_id: str | None = (subscription.get("metadata") or {}).get("org_id")

        if not org_id:
            logger.warning("billing: customer.subscription.deleted missing org_id in metadata")
            return

        org = await db.get(Organization, org_id)
        if org is None:
            logger.warning("billing: org %s not found for subscription.deleted", org_id)
            return

        org.plan_tier = "free"
        org.stripe_subscription_id = None
        await db.commit()
        logger.info("billing: org %s downgraded to free (subscription deleted)", org_id)

    async def _on_payment_failed(self, invoice: dict, db: AsyncSession) -> None:
        """Handle invoice.payment_failed — email org owner with a portal link."""
        customer_id: str | None = invoice.get("customer")
        if not customer_id:
            logger.warning("billing: invoice.payment_failed missing customer")
            return

        result = await db.execute(
            select(Organization).where(Organization.stripe_customer_id == customer_id)
        )
        org = result.scalar_one_or_none()
        if org is None:
            logger.warning(
                "billing: no org found for stripe_customer_id=%s (invoice.payment_failed)",
                customer_id,
            )
            return

        # Owner resolved via memberships (users.org_id/role are only the
        # active-org projection).  limit(1) also fixes a pre-existing crash:
        # scalar_one_or_none raises MultipleResultsFound for multi-owner orgs.
        owner_result = await db.execute(
            select(User)
            .join(OrgMembership, OrgMembership.user_id == User.id)
            .where(
                OrgMembership.org_id == org.id,
                OrgMembership.role == "owner",
                User.is_active.is_(True),
            )
            .order_by(OrgMembership.created_at.asc())
            .limit(1)
        )
        owner = owner_result.scalar_one_or_none()
        if owner is None:
            logger.warning("billing: no owner found for org %s (invoice.payment_failed)", org.id)
            return

        return_url = settings.frontend_url + "/settings?tab=billing"
        portal_session = await asyncio.to_thread(
            stripe.billing_portal.Session.create,
            customer=customer_id,
            return_url=return_url,
        )

        await send_payment_failed(
            to=owner.email,
            org_name=org.name,
            portal_url=portal_session.url,
        )
        logger.info("billing: payment_failed email sent to %s for org %s", owner.email, org.id)
