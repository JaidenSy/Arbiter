"""
Arbiter — Email service.

Sends transactional emails via the Resend HTTP API (https://resend.com).
Using HTTP instead of SMTP avoids port-blocking issues on cloud platforms
(Railway, Render, etc.) that restrict outbound SMTP connections.

When RESEND_API_KEY is not set all send calls are no-ops that log a warning —
the application continues to work without email in development.
"""

from __future__ import annotations

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_RESEND_URL = "https://api.resend.com/emails"


async def send_email(to: str, subject: str, html: str, text: str = "") -> None:
    if not settings.email_enabled:
        logger.warning(
            "email: RESEND_API_KEY not set — skipping send to %s (subject: %s)", to, subject
        )
        return

    payload: dict = {
        "from": f"{settings.email_from_name} <{settings.email_from}>",
        "to": [to],
        "subject": subject,
        "html": html,
    }
    if text:
        payload["text"] = text

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            _RESEND_URL,
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json=payload,
        )

    if response.status_code not in (200, 201):
        logger.error("email: Resend API error %s — %s", response.status_code, response.text)
        response.raise_for_status()


async def send_password_reset(to: str, reset_url: str) -> None:
    html = f"""
<p>You requested a password reset for your Arbiter account.</p>
<p><a href="{reset_url}">Reset your password</a></p>
<p>This link expires in 1 hour. If you didn't request this, ignore this email.</p>
"""
    text = f"Reset your Arbiter password: {reset_url}\n\nExpires in 1 hour."
    await send_email(to, "Reset your Arbiter password", html, text)


async def send_email_verification(to: str, verify_url: str) -> None:
    html = f"""
<p>Welcome to Arbiter! Please verify your email address.</p>
<p><a href="{verify_url}">Verify email</a></p>
<p>This link expires in 24 hours.</p>
"""
    text = f"Verify your Arbiter email: {verify_url}"
    await send_email(to, "Verify your Arbiter email", html, text)


async def send_org_invite(to: str, invited_by: str, org_name: str, accept_url: str) -> None:
    html = f"""
<p><strong>{invited_by}</strong> invited you to join <strong>{org_name}</strong> on Arbiter.</p>
<p><a href="{accept_url}">Accept invitation</a></p>
<p>This invitation expires in 7 days.</p>
"""
    text = f"{invited_by} invited you to {org_name} on Arbiter.\nAccept: {accept_url}"
    await send_email(to, f"You're invited to {org_name} on Arbiter", html, text)


async def send_email_change_confirmation(to: str, confirm_url: str) -> None:
    html = f"""
<p>You requested to change your Arbiter email address.</p>
<p><a href="{confirm_url}">Confirm your new email address</a></p>
<p>This link expires in 24 hours. If you didn't request this, ignore this email — your current address remains active.</p>
"""
    text = f"Confirm your new Arbiter email: {confirm_url}\n\nExpires in 24 hours."
    await send_email(to, "Confirm your new email address — Arbiter", html, text)


async def send_payment_failed(to: str, org_name: str, portal_url: str) -> None:
    html = f"""
<p>We were unable to process the payment for <strong>{org_name}</strong>'s Arbiter Pro subscription.</p>
<p>Your Pro access is at risk. Please update your payment method to avoid losing access.</p>
<p><a href="{portal_url}">Update payment method</a></p>
<p>If you need help, reply to this email.</p>
"""
    text = (
        f"Payment failed for {org_name}'s Arbiter Pro subscription.\n"
        f"Update your payment method to keep Pro access: {portal_url}"
    )
    await send_email(to, "Action required: payment failed for Arbiter Pro", html, text)
