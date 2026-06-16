"""
Arbiter — API endpoints: Orgs, Members & Invites.

Membership model: users may belong to multiple organizations via
org_memberships (source of truth for access + per-org role).  The
``users.org_id`` / ``users.role`` columns are the *active-org projection* —
the org the user currently operates in — and every mutation here keeps the
projection in sync.  Plans and billing attach to orgs, never to members.

Routes:
    GET    /org                      — get active organization info
    PATCH  /org                      — rename organization (owner only)
    POST   /org                      — create a new organization and switch to it
    POST   /org/switch               — switch the active organization
    POST   /org/leave                — leave the active organization
    GET    /me/orgs                  — list the caller's organizations
    GET    /org/members              — list all members
    PATCH  /org/members/{id}         — change a member's role
    DELETE /org/members/{id}         — remove a member
    GET    /org/invites              — list pending invites
    POST   /org/invites              — send an invite email
    DELETE /org/invites/{id}         — cancel an invite
    POST   /auth/accept-invite       — accept an invite (new or existing account)
"""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security as _sec
from app.core.config import settings
from app.core.dependencies import (
    get_current_user,
    get_current_user_optional,
    get_db,
    get_redis,
    require_role,
)
from app.core.password import validate_password_strength
from app.db.models.agent import Agent
from app.db.models.org_invite import OrgInvite
from app.db.models.org_membership import OrgMembership
from app.db.models.organization import Organization
from app.db.models.user import User
from app.schemas.auth import TokenResponse
from app.schemas.pagination import Page
from app.services.auth import auth_service
from app.services.email.email_service import send_org_invite
from app.services.org import org_service

router = APIRouter(tags=["org"])

_VALID_ROLES = {"owner", "admin", "member"}

# Mirrors the registration limit: each new org gets a fresh free-tier quota,
# so unbounded org creation would be a quota-reset loophole.
_ORG_CREATE_DAILY_LIMIT = 3


# ── Schemas ───────────────────────────────────────────────────────────────────


class OrgResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    plan_tier: str
    created_at: datetime

    model_config = {"from_attributes": True}


class RenameOrgRequest(BaseModel):
    name: str


class CreateOrgRequest(BaseModel):
    name: str


class SwitchOrgRequest(BaseModel):
    org_id: uuid.UUID


class MyOrgResponse(BaseModel):
    org_id: uuid.UUID
    name: str
    slug: str
    plan_tier: str
    role: str
    joined_at: datetime
    is_current: bool


class MemberResponse(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str | None
    role: str
    is_verified: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UpdateMemberRequest(BaseModel):
    role: str


class InviteRequest(BaseModel):
    email: EmailStr
    role: str = "member"


class InviteResponse(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    created_at: datetime
    expires_at: datetime
    accepted_at: datetime | None

    model_config = {"from_attributes": True}


class AcceptInviteRequest(BaseModel):
    token: str
    display_name: str | None = None
    # Required when the invite email has no account yet; ignored otherwise.
    password: str | None = None


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _deactivate_member_agents(
    db: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """
    Deactivate all agents the user created in this org so their API keys can
    no longer make proxy calls after the user departs.
    """
    await db.execute(
        update(Agent)
        .where(
            Agent.org_id == org_id,
            Agent.created_by_user_id == user_id,
            Agent.is_active.is_(True),
        )
        .values(is_active=False)
    )


async def _reassign_member_resources(
    db: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """
    Reassign agents the departing user created in this org to the org owner.

    VaultSecret and MCPServer belong to the org by design (no created_by
    column) — they are unaffected.  Only Agent tracks the creating user, so
    this function transfers authorship to the current org owner so the
    resources are not orphaned when the member leaves.

    If no owner membership exists (should not happen in practice) the
    created_by_user_id is left unchanged.
    """
    owner_id: uuid.UUID | None = await db.scalar(
        select(OrgMembership.user_id).where(
            OrgMembership.org_id == org_id,
            OrgMembership.role == "owner",
        )
    )
    if owner_id is None:
        return
    await db.execute(
        update(Agent)
        .where(
            Agent.org_id == org_id,
            Agent.created_by_user_id == user_id,
        )
        .values(created_by_user_id=owner_id)
    )


async def _consume_invite(db: AsyncSession, token: str) -> OrgInvite:
    """
    Atomically mark an invite as accepted — prevents TOCTOU race where two
    simultaneous requests both pass an accepted_at IS NULL check.  Only the
    first UPDATE to win finds a matching row.

    Raises:
        HTTPException 400: invalid token, or already used / expired.
    """
    accept_result = await db.execute(
        update(OrgInvite)
        .where(
            OrgInvite.token == token,
            OrgInvite.accepted_at.is_(None),
            OrgInvite.expires_at > datetime.now(tz=UTC),
        )
        .values(accepted_at=datetime.now(tz=UTC))
        .returning(OrgInvite)
    )
    invite = accept_result.scalar_one_or_none()
    if invite is None:
        token_exists = await db.scalar(select(OrgInvite).where(OrgInvite.token == token))
        if token_exists is None:
            raise HTTPException(status_code=400, detail="Invalid invite token")
        raise HTTPException(status_code=400, detail="Invite already used or expired")
    return invite


# ── Org ───────────────────────────────────────────────────────────────────────


@router.get("/org", response_model=OrgResponse, summary="Get organization info")
async def get_org(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OrgResponse:
    org = await db.get(Organization, current_user.org_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return OrgResponse.model_validate(org)


@router.patch("/org", response_model=OrgResponse, summary="Rename organization (owner only)")
async def rename_org(
    body: RenameOrgRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner")),
) -> OrgResponse:
    name = body.name.strip()
    if not name or len(name) > 255:
        raise HTTPException(status_code=422, detail="Name must be 1–255 characters")
    org = await db.get(Organization, current_user.org_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    org.name = name
    await db.commit()
    await db.refresh(org)
    return OrgResponse.model_validate(org)


@router.post(
    "/org",
    response_model=OrgResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new organization and switch to it",
)
async def create_org(
    body: CreateOrgRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    redis=Depends(get_redis),
) -> OrgResponse:
    name = body.name.strip()
    if not name or len(name) > 255:
        raise HTTPException(status_code=422, detail="Name must be 1–255 characters")

    # Lifetime owned-org cap — DB-backed, so it holds even when Redis is down.
    # Closes the free-tier quota-multiplication vector (minting unbounded free
    # orgs); tiered so paid owners get a higher ceiling. Only ever blocks the
    # NEXT org — existing orgs are never touched.
    owned = await org_service.count_owned_orgs(db, current_user.id)
    limit = await org_service.owned_org_limit_for_user(db, current_user.id)
    if owned >= limit:
        if limit > settings.free_owned_org_limit:
            detail = (
                f"You have reached the maximum of {limit} organizations. "
                "Contact support to raise this limit."
            )
        else:
            detail = (
                f"Free accounts can own up to {limit} organizations. "
                "Upgrade an organization to Pro to create more."
            )
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=detail)

    # Daily create rate-limit. Redis is the fast path; when it is unavailable we
    # fall back to a DB count so the limit fails CLOSED (never silently lifts).
    if redis is not None:
        create_key = f"org_create:{current_user.id}:{date.today().isoformat()}"
        create_count = await redis.incr(create_key)
        if create_count == 1:
            await redis.expire(create_key, 86400)  # 24-hour window
        if create_count > _ORG_CREATE_DAILY_LIMIT:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many organizations created today. Try again tomorrow.",
            )
    else:
        since = datetime.now(UTC) - timedelta(days=1)
        recent = await org_service.count_owned_orgs_since(db, current_user.id, since)
        if recent >= _ORG_CREATE_DAILY_LIMIT:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many organizations created today. Try again tomorrow.",
            )

    org = await org_service.create_org(db, name)
    await org_service.add_membership(
        db, user=current_user, org_id=org.id, role="owner", set_active=True
    )
    await db.commit()
    await db.refresh(org)
    return OrgResponse.model_validate(org)


@router.post(
    "/org/switch",
    response_model=TokenResponse,
    summary="Switch the active organization",
)
async def switch_org(
    body: SwitchOrgRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TokenResponse:
    membership = await org_service.get_membership(db, current_user.id, body.org_id)
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of that organization",
        )
    org = await db.get(Organization, body.org_id)
    if org is None or not org.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization is suspended",
        )

    org_service.set_active_membership(current_user, membership)
    await db.commit()

    access_token, refresh_token = await auth_service.create_token_pair(db=db, user=current_user)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post(
    "/org/leave",
    response_model=TokenResponse,
    summary="Leave the active organization",
)
async def leave_org(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TokenResponse:
    membership = await org_service.get_membership(db, current_user.id, current_user.org_id)
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You are not a member of this organization",
        )

    if membership.role == "owner":
        other_owners = await org_service.count_other_owners(
            db, current_user.org_id, excluding_user_id=current_user.id
        )
        if other_owners == 0:
            raise HTTPException(
                status_code=400,
                detail=(
                    "You are the only owner of this organization. "
                    "Promote another member to owner first, or delete your "
                    "account to delete the organization."
                ),
            )

    org_id = current_user.org_id
    await db.delete(membership)
    await db.flush()

    # Deactivate BEFORE reassigning: both helpers filter on created_by_user_id,
    # so once reassignment rewrites it to the owner, deactivation matches nothing
    # and the departing member's API keys stay live.
    await _deactivate_member_agents(db, org_id, current_user.id)
    await _reassign_member_resources(db, org_id, current_user.id)
    await org_service.repoint_active_org(db, current_user)
    await db.commit()

    access_token, refresh_token = await auth_service.create_token_pair(db=db, user=current_user)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.get(
    "/me/orgs",
    response_model=list[MyOrgResponse],
    summary="List the organizations the caller belongs to",
)
async def list_my_orgs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[MyOrgResponse]:
    result = await db.execute(
        select(OrgMembership, Organization)
        .join(Organization, Organization.id == OrgMembership.org_id)
        .where(OrgMembership.user_id == current_user.id, Organization.is_active.is_(True))
        .order_by(OrgMembership.created_at.asc())
    )
    return [
        MyOrgResponse(
            org_id=org.id,
            name=org.name,
            slug=org.slug,
            plan_tier=org.plan_tier,
            role=membership.role,
            joined_at=membership.created_at,
            is_current=org.id == current_user.org_id,
        )
        for membership, org in result.all()
    ]


# ── Members ───────────────────────────────────────────────────────────────────


@router.get("/org/members", response_model=Page[MemberResponse], summary="List org members")
async def list_members(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Page[MemberResponse]:
    base_filter = (
        OrgMembership.org_id == current_user.org_id,
        User.is_active.is_(True),
    )
    total = (
        await db.scalar(
            select(func.count(OrgMembership.id))
            .join(User, User.id == OrgMembership.user_id)
            .where(*base_filter)
        )
        or 0
    )
    result = await db.execute(
        select(User, OrgMembership)
        .join(OrgMembership, OrgMembership.user_id == User.id)
        .where(*base_filter)
        .order_by(OrgMembership.created_at.asc())
        .offset(skip)
        .limit(limit)
    )
    items = [
        MemberResponse(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            role=membership.role,
            is_verified=user.is_verified,
            created_at=membership.created_at,
        )
        for user, membership in result.all()
    ]
    return Page(items=items, total=total, skip=skip, limit=limit)


@router.patch(
    "/org/members/{member_id}", response_model=MemberResponse, summary="Update a member's role"
)
async def update_member(
    member_id: uuid.UUID,
    body: UpdateMemberRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner", "admin")),
) -> MemberResponse:
    if body.role not in _VALID_ROLES:
        raise HTTPException(
            status_code=422, detail=f"Invalid role. Must be one of: {sorted(_VALID_ROLES)}"
        )

    membership = await org_service.get_membership(db, member_id, current_user.org_id)
    member = await db.get(User, member_id)
    if membership is None or member is None or not member.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    # Prevent privilege escalation
    if member.id == current_user.id and body.role == "owner":
        raise HTTPException(status_code=403, detail="Cannot self-promote to owner")
    # Admins cannot assign owner role
    if current_user.role == "admin" and body.role == "owner":
        raise HTTPException(status_code=403, detail="Only owners can assign owner role")

    # Prevent stripping the last owner
    if membership.role == "owner" and body.role != "owner":
        other_owners = await org_service.count_other_owners(
            db, current_user.org_id, excluding_user_id=member.id
        )
        if other_owners == 0:
            raise HTTPException(status_code=400, detail="Cannot demote the last owner")

    membership.role = body.role
    # Keep the active-org projection in sync when this org is the member's
    # currently selected one.
    if member.org_id == current_user.org_id:
        member.role = body.role
    await db.commit()
    await db.refresh(membership)
    return MemberResponse(
        id=member.id,
        email=member.email,
        display_name=member.display_name,
        role=membership.role,
        is_verified=member.is_verified,
        created_at=membership.created_at,
    )


@router.delete(
    "/org/members/{member_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Remove a member",
)
async def remove_member(
    member_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner", "admin")),
) -> Response:
    if member_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot remove yourself — use leave instead")

    membership = await org_service.get_membership(db, member_id, current_user.org_id)
    member = await db.get(User, member_id)
    if membership is None or member is None or not member.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    if membership.role == "owner":
        other_owners = await org_service.count_other_owners(
            db, current_user.org_id, excluding_user_id=member.id
        )
        if other_owners == 0:
            raise HTTPException(status_code=400, detail="Cannot remove the last owner")

    org_id = current_user.org_id
    await db.delete(membership)
    await db.flush()

    # Their account survives — only the membership is removed.  Agents the
    # member created are deactivated so their keys stop working here, then
    # reassigned to the org owner so they are not orphaned.  Deactivation must
    # run first: both helpers filter on created_by_user_id, so reassigning
    # first would rewrite it to the owner and deactivation would match nothing.
    await _deactivate_member_agents(db, org_id, member.id)
    await _reassign_member_resources(db, org_id, member.id)

    if member.org_id == org_id:
        await org_service.repoint_active_org(db, member)

    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Invites ───────────────────────────────────────────────────────────────────


@router.get("/org/invites", response_model=Page[InviteResponse], summary="List pending invites")
async def list_invites(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner", "admin")),
) -> Page[InviteResponse]:
    total = (
        await db.scalar(
            select(func.count(OrgInvite.id)).where(
                OrgInvite.org_id == current_user.org_id, OrgInvite.accepted_at.is_(None)
            )
        )
        or 0
    )
    result = await db.execute(
        select(OrgInvite)
        .where(OrgInvite.org_id == current_user.org_id, OrgInvite.accepted_at.is_(None))
        .order_by(OrgInvite.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return Page(
        items=[InviteResponse.model_validate(i) for i in result.scalars().all()],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post(
    "/org/invites",
    response_model=InviteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Invite a new member",
)
async def create_invite(
    body: InviteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner", "admin")),
) -> InviteResponse:
    if body.role not in _VALID_ROLES:
        raise HTTPException(
            status_code=422, detail=f"Invalid role. Must be one of: {sorted(_VALID_ROLES)}"
        )

    # Only owners can invite other owners
    if body.role == "owner" and current_user.role != "owner":
        raise HTTPException(status_code=403, detail="Only owners can invite other owners")

    # Reject inviting someone who is already a member of this org.
    invitee = await db.scalar(select(User).where(User.email == body.email))
    if invitee is not None:
        existing_membership = await org_service.get_membership(db, invitee.id, current_user.org_id)
        if existing_membership is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"{body.email} is already a member of this organization",
            )

    # Dedup: prevent multiple pending invites to the same email in the same org
    existing_invite = await db.scalar(
        select(OrgInvite).where(
            OrgInvite.org_id == current_user.org_id,
            OrgInvite.email == body.email,
            OrgInvite.accepted_at.is_(None),
            OrgInvite.expires_at > datetime.now(tz=UTC),
        )
    )
    if existing_invite is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A pending invite for {body.email} already exists. Cancel it first or wait for it to expire.",
        )

    token = secrets.token_urlsafe(48)
    expires_at = datetime.now(tz=UTC) + timedelta(days=7)

    invite = OrgInvite(
        org_id=current_user.org_id,
        invited_by_user_id=current_user.id,
        email=body.email,
        role=body.role,
        token=token,
        expires_at=expires_at,
    )
    db.add(invite)
    await db.commit()
    await db.refresh(invite)

    org = await db.get(Organization, current_user.org_id)
    accept_url = f"{settings.frontend_url}/accept-invite?token={token}"
    await send_org_invite(
        to=body.email,
        invited_by=current_user.display_name or current_user.email,
        org_name=org.name if org else "your team",
        accept_url=accept_url,
    )

    return InviteResponse.model_validate(invite)


@router.delete(
    "/org/invites/{invite_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Cancel an invite",
)
async def cancel_invite(
    invite_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner", "admin")),
) -> Response:
    result = await db.execute(
        select(OrgInvite).where(OrgInvite.id == invite_id, OrgInvite.org_id == current_user.org_id)
    )
    invite = result.scalar_one_or_none()
    if invite is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found")
    await db.delete(invite)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Accept invite (public; optional auth for existing accounts) ───────────────

_accept_router = APIRouter(prefix="/auth", tags=["auth"])


class InvitePreviewResponse(BaseModel):
    """Lightweight org context shown to the user before they accept an invite."""

    org_name: str
    plan_tier: str
    role: str
    email: str


@_accept_router.get(
    "/invite-preview",
    response_model=InvitePreviewResponse,
    summary="Preview org details for a pending invite (does not consume the token)",
)
async def invite_preview(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> InvitePreviewResponse:
    """
    Return the org name, plan tier, role, and invited email for a valid invite
    token without consuming it.  Used by the frontend to show a confirmation
    dialog before the user accepts.
    """
    invite = await db.scalar(select(OrgInvite).where(OrgInvite.token == token))
    if invite is None:
        raise HTTPException(status_code=400, detail="Invalid invite token")
    now = datetime.now(tz=UTC)
    if invite.accepted_at is not None or invite.expires_at.replace(tzinfo=UTC) <= now:
        raise HTTPException(status_code=400, detail="Invite already used or expired")

    org = await db.get(Organization, invite.org_id)
    if org is None or not org.is_active:
        raise HTTPException(status_code=400, detail="Organization not found or suspended")

    return InvitePreviewResponse(
        org_name=org.name,
        plan_tier=org.plan_tier,
        role=invite.role,
        email=invite.email,
    )


@_accept_router.post(
    "/accept-invite",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Accept an org invite — creates an account, or joins with an existing one",
)
async def accept_invite(
    body: AcceptInviteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
) -> TokenResponse:
    # ── Validation phase (does not consume the invite) ────────────────────────
    invite_preview = await db.scalar(select(OrgInvite).where(OrgInvite.token == body.token))
    if invite_preview is None:
        raise HTTPException(status_code=400, detail="Invalid invite token")
    now = datetime.now(tz=UTC)
    if (
        invite_preview.accepted_at is not None
        or invite_preview.expires_at.replace(tzinfo=UTC) <= now
    ):
        raise HTTPException(status_code=400, detail="Invite already used or expired")

    existing = await db.scalar(select(User).where(User.email == invite_preview.email))

    if existing is not None:
        # ── Existing account: join the org as an additional membership ───────
        if not existing.is_active:
            raise HTTPException(status_code=403, detail="This account has been deactivated")
        # 409 (not 401): the global 401 handler rewrites details to a generic
        # message for security, which would swallow this actionable hint.
        if current_user is None or current_user.id != existing.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"An account with {invite_preview.email} already exists. "
                    "Log in to that account and retry to join the organization."
                ),
            )
        if await org_service.get_membership(db, existing.id, invite_preview.org_id) is not None:
            raise HTTPException(
                status_code=409, detail="You are already a member of this organization"
            )

        invite = await _consume_invite(db, body.token)
        await org_service.add_membership(
            db, user=existing, org_id=invite.org_id, role=invite.role, set_active=True
        )
        user = existing
    else:
        # ── No account yet: create one inside the inviting org ───────────────
        if body.password is None:
            raise HTTPException(status_code=422, detail="Password is required to create an account")
        try:
            validate_password_strength(body.password)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        invite = await _consume_invite(db, body.token)
        user = User(
            org_id=invite.org_id,
            email=invite.email,
            display_name=body.display_name,
            hashed_password=_sec.hash_password(body.password),
            role=invite.role,
            is_active=True,
            is_verified=True,  # invited users are pre-verified via email
        )
        db.add(user)
        await db.flush()
        await org_service.add_membership(db, user=user, org_id=invite.org_id, role=invite.role)

    await db.commit()
    await db.refresh(user)

    access_token, refresh_token = await auth_service.create_token_pair(db=db, user=user)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )
