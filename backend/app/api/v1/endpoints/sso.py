"""
NexusAI — API endpoints: SSO (Social Login).

Implements Google (OIDC) and GitHub (OAuth2) social login via Authlib.
The full OAuth2 dance is handled server-side; the React frontend only
navigates to the provider redirect URLs and receives a short-lived
one-time token on the callback.

Routes:
    GET  /auth/providers          → { google: bool, github: bool }
    GET  /auth/google             → redirect to Google consent page
    GET  /auth/google/callback    → handle Google callback, issue OTT, redirect
    GET  /auth/github             → redirect to GitHub authorization page
    GET  /auth/github/callback    → handle GitHub callback, issue OTT, redirect
    POST /auth/sso/exchange       → exchange OTT for JWT + refresh token
"""

from __future__ import annotations

import logging

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_db, get_redis
from app.schemas.auth import TokenResponse
from app.services.auth import sso_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["sso"])

# ── Authlib OAuth registry ────────────────────────────────────────────────────

oauth = OAuth()

# Google — OIDC, discovery-based
oauth.register(
    name="google",
    client_id=settings.google_client_id or None,
    client_secret=settings.google_client_secret or None,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={
        "scope": "openid email profile",
    },
)

# GitHub — plain OAuth2, no OIDC discovery
oauth.register(
    name="github",
    client_id=settings.github_client_id or None,
    client_secret=settings.github_client_secret or None,
    authorize_url="https://github.com/login/oauth/authorize",
    access_token_url="https://github.com/login/oauth/access_token",
    api_base_url="https://api.github.com/",
    client_kwargs={
        "scope": "user:email",
    },
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _google_configured() -> bool:
    return bool(settings.google_client_id and settings.google_client_secret)


def _github_configured() -> bool:
    return bool(settings.github_client_id and settings.github_client_secret)


def _redirect_error(message: str = "sso_failed") -> RedirectResponse:
    return RedirectResponse(
        url=f"{settings.frontend_url}/login?error={message}",
        status_code=status.HTTP_302_FOUND,
    )


# ── Provider availability ─────────────────────────────────────────────────────


@router.get(
    "/providers",
    summary="List configured OAuth2 providers",
    status_code=status.HTTP_200_OK,
)
async def list_providers() -> dict[str, bool]:
    """
    Return which social login providers are currently configured.

    The frontend uses this to conditionally show / hide social login buttons.

    Returns:
        { "google": bool, "github": bool }
    """
    return {
        "google": _google_configured(),
        "github": _github_configured(),
    }


# ── Google ─────────────────────────────────────────────────────────────────────


@router.get("/google", summary="Redirect to Google OAuth2 consent page")
async def google_login(request: Request) -> RedirectResponse:
    """
    Initiate Google OIDC login.

    Builds the Google authorization URL (with state) and redirects the browser.
    Returns 503 if Google credentials are not configured.
    """
    if not _google_configured():
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"error": "provider_not_configured"},
        )

    redirect_uri = f"{settings.oauth_redirect_base_url}/api/v1/auth/google/callback"
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/google/callback", summary="Handle Google OAuth2 callback")
async def google_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> RedirectResponse:
    """
    Complete the Google OIDC flow.

    Exchanges the authorization code for an ID token, extracts user info,
    provisions the user if needed, issues a one-time token, and redirects
    the browser to the frontend callback page.
    """
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception as exc:
        logger.warning("Google OAuth callback error: %s", exc)
        return _redirect_error()

    user_info = token.get("userinfo")
    if not user_info:
        try:
            user_info = await oauth.google.userinfo(token=token)
        except Exception as exc:
            logger.warning("Google userinfo fetch error: %s", exc)
            return _redirect_error()

    email: str | None = user_info.get("email")
    if not email:
        logger.warning("Google SSO: no email in userinfo")
        return _redirect_error()

    provider_user_id: str = str(user_info.get("sub", ""))
    name: str = user_info.get("name", "") or email.split("@")[0]
    avatar_url: str | None = user_info.get("picture")

    try:
        user = await sso_service.get_or_create_user(
            db=db,
            provider="google",
            provider_user_id=provider_user_id,
            email=email,
            name=name,
            avatar_url=avatar_url,
        )
    except Exception as exc:
        logger.warning("Google SSO user provisioning error: %s", exc)
        return _redirect_error()

    ott = await sso_service.issue_one_time_token(redis, str(user.id))
    return RedirectResponse(
        url=f"{settings.frontend_url}/auth/callback?token={ott}",
        status_code=status.HTTP_302_FOUND,
    )


# ── GitHub ─────────────────────────────────────────────────────────────────────


@router.get("/github", summary="Redirect to GitHub OAuth2 authorization page")
async def github_login(request: Request) -> RedirectResponse:
    """
    Initiate GitHub OAuth2 login.

    Builds the GitHub authorization URL (with state) and redirects the browser.
    Returns 503 if GitHub credentials are not configured.
    """
    if not _github_configured():
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"error": "provider_not_configured"},
        )

    redirect_uri = f"{settings.oauth_redirect_base_url}/api/v1/auth/github/callback"
    return await oauth.github.authorize_redirect(request, redirect_uri)


@router.get("/github/callback", summary="Handle GitHub OAuth2 callback")
async def github_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> RedirectResponse:
    """
    Complete the GitHub OAuth2 flow.

    Exchanges the authorization code for an access token, calls the GitHub
    /user API endpoint for profile data, falls back to /user/emails if the
    primary email is private, provisions the user, issues a one-time token,
    and redirects the browser to the frontend callback page.
    """
    try:
        token = await oauth.github.authorize_access_token(request)
    except Exception as exc:
        logger.warning("GitHub OAuth callback error: %s", exc)
        return _redirect_error()

    try:
        resp = await oauth.github.get("user", token=token)
        resp.raise_for_status()
        profile = resp.json()
    except Exception as exc:
        logger.warning("GitHub user profile fetch error: %s", exc)
        return _redirect_error()

    email: str | None = profile.get("email")

    # GitHub users with private emails: fall back to /user/emails
    if not email:
        try:
            emails_resp = await oauth.github.get("user/emails", token=token)
            emails_resp.raise_for_status()
            emails_data = emails_resp.json()
            # Pick the primary verified email
            for entry in emails_data:
                if entry.get("primary") and entry.get("verified"):
                    email = entry.get("email")
                    break
            # If no primary verified, take first verified
            if not email:
                for entry in emails_data:
                    if entry.get("verified"):
                        email = entry.get("email")
                        break
        except Exception as exc:
            logger.warning("GitHub /user/emails fetch error: %s", exc)

    if not email:
        logger.warning("GitHub SSO: could not determine user email")
        return _redirect_error()

    provider_user_id: str = str(profile.get("id", ""))
    name: str = profile.get("name", "") or profile.get("login", "") or email.split("@")[0]
    avatar_url: str | None = profile.get("avatar_url")

    try:
        user = await sso_service.get_or_create_user(
            db=db,
            provider="github",
            provider_user_id=provider_user_id,
            email=email,
            name=name,
            avatar_url=avatar_url,
        )
    except Exception as exc:
        logger.warning("GitHub SSO user provisioning error: %s", exc)
        return _redirect_error()

    ott = await sso_service.issue_one_time_token(redis, str(user.id))
    return RedirectResponse(
        url=f"{settings.frontend_url}/auth/callback?token={ott}",
        status_code=status.HTTP_302_FOUND,
    )


# ── OTT exchange ───────────────────────────────────────────────────────────────


class OTTExchangeRequest(BaseModel):
    token: str


@router.post(
    "/sso/exchange",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Exchange one-time token for JWT + refresh token",
)
async def exchange_ott(
    body: OTTExchangeRequest,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> TokenResponse:
    """
    Consume a one-time token issued after a successful OAuth2 callback.

    The OTT is single-use and expires after 60 seconds.  On success, returns
    a standard JWT access token + opaque refresh token pair — identical shape
    to the email/password login response so the frontend can handle both flows
    with the same code path.

    Args:
        body:  { token: "ott_<hex>" }
        db:    Injected database session.
        redis: Injected Redis client.

    Returns:
        TokenResponse: access_token, refresh_token, token_type, expires_in.

    Raises:
        HTTPException 400: If the token is invalid or expired.
        HTTPException 401: If the linked user is inactive.
    """
    _user, access_token, refresh_token = await sso_service.exchange_one_time_token(
        redis=redis,
        db=db,
        raw_token=body.token,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )
