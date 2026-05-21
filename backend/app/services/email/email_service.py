"""
Arbiter — Email service.

Sends transactional emails via SMTP (TLS/STARTTLS).  When SMTP is not
configured (smtp_host is empty) all send calls are no-ops that log a
warning — the application continues to work without email in development.

Uses run_in_executor to avoid blocking the async event loop.
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger(__name__)


def _send_sync(to: str, subject: str, html: str, text: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    msg["To"] = to
    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.ehlo()
        server.starttls()
        server.login(settings.smtp_user, settings.smtp_password)
        server.sendmail(settings.smtp_from_email, to, msg.as_string())


async def send_email(to: str, subject: str, html: str, text: str = "") -> None:
    if not settings.email_enabled:
        logger.warning("email: SMTP not configured — skipping send to %s (subject: %s)", to, subject)
        return
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _send_sync, to, subject, html, text or subject)


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
