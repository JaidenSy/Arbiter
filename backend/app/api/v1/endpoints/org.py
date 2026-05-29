"""
Arbiter — API endpoints: Org Members & Invites.

Routes:
    GET    /org                      — get organization info
    PATCH  /org                      — rename organization (owner only)
    GET    /org/members              — list all members
    PATCH  /org/members/{id}         — change a member's role
    DELETE /org/members/{id}         — remove a member
    GET    /org/invites              — list pending invites
    POST   /org/invites              — send an invite email
    DELETE /org/invites/{id}         — cancel an invite
    POST   /auth/accept-invite       — accept an invite and create account
"""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from itsdangerous import URLSafeTimedSerializer
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security as _sec
from app.core.config import settings
from app.core.dependencies import get_current_user, get_db, require_role
from app.schemas.pagination import Page
from app.db.models.agent import Agent
from app.db.models.org_invite import OrgInvite
from app.db.models.organization import Organization
from app.db.models.user import User
from app.schemas.auth import TokenResponse
from app.services.auth import auth_service
from app.services.email.email_service import send_org_invite

router = APIRouter(tags=["org"])

_VALID_ROLES = {"owner", "admin", "member"}


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
    password: str


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


# ── Members ───────────────────────────────────────────────────────────────────


@router.get("/org/members", response_model=Page[MemberResponse], summary="List org members")
async def list_members(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Page[MemberResponse]:
    total = await db.scalar(
        select(func.count(User.id)).where(User.org_id == current_user.org_id, User.is_active.is_(True))
    ) or 0
    result = await db.execute(
        select(User)
        .where(User.org_id == current_user.org_id, User.is_active.is_(True))
        .order_by(User.created_at.asc())
        .offset(skip)
        .limit(limit)
    )
    return Page(items=[MemberResponse.model_validate(u) for u in result.scalars().all()], total=total, skip=skip, limit=limit)


@router.patch("/org/members/{member_id}", response_model=MemberResponse, summary="Update a member's role")
async def update_member(
    member_id: uuid.UUID,
    body: UpdateMemberRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner", "admin")),
) -> MemberResponse:
    if body.role not in _VALID_ROLES:
        raise HTTPException(status_code=422, detail=f"Invalid role. Must be one of: {sorted(_VALID_ROLES)}")

    result = await db.execute(
        select(User).where(User.id == member_id, User.org_id == current_user.org_id, User.is_active.is_(True))
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    # Prevent stripping the last owner
    if member.role == "owner" and body.role != "owner":
        owners = await db.execute(
            select(User).where(User.org_id == current_user.org_id, User.role == "owner", User.is_active.is_(True))
        )
        if len(owners.scalars().all()) <= 1:
            raise HTTPException(status_code=400, detail="Cannot demote the last owner")

    member.role = body.role
    await db.commit()
    await db.refresh(member)
    return MemberResponse.model_validate(member)


@router.delete("/org/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None, summary="Remove a member")
async def remove_member(
    member_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner", "admin")),
) -> Response:
    if member_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot remove yourself")

    result = await db.execute(
        select(User).where(User.id == member_id, User.org_id == current_user.org_id, User.is_active.is_(True))
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    if member.role == "owner":
        owners = await db.execute(
            select(User).where(User.org_id == current_user.org_id, User.role == "owner", User.is_active.is_(True))
        )
        if len(owners.scalars().all()) <= 1:
            raise HTTPException(status_code=400, detail="Cannot remove the last owner")

    member.is_active = False

    # Deactivate all agents created by the removed member within this org so
    # their API keys can no longer be used to make proxy calls.
    await db.execute(
        update(Agent)
        .where(
            Agent.org_id == current_user.org_id,
            Agent.created_by_user_id == member.id,
            Agent.is_active.is_(True),
        )
        .values(is_active=False)
    )

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
    total = await db.scalar(
        select(func.count(OrgInvite.id)).where(
            OrgInvite.org_id == current_user.org_id, OrgInvite.accepted_at.is_(None)
        )
    ) or 0
    result = await db.execute(
        select(OrgInvite)
        .where(OrgInvite.org_id == current_user.org_id, OrgInvite.accepted_at.is_(None))
        .order_by(OrgInvite.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return Page(items=[InviteResponse.model_validate(i) for i in result.scalars().all()], total=total, skip=skip, limit=limit)


@router.post("/org/invites", response_model=InviteResponse, status_code=status.HTTP_201_CREATED, summary="Invite a new member")
async def create_invite(
    body: InviteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner", "admin")),
) -> InviteResponse:
    if body.role not in _VALID_ROLES:
        raise HTTPException(status_code=422, detail=f"Invalid role. Must be one of: {sorted(_VALID_ROLES)}")

    # Only owners can invite other owners
    if body.role == "owner" and current_user.role != "owner":
        raise HTTPException(status_code=403, detail="Only owners can invite other owners")

    # Dedup: prevent multiple pending invites to the same email in the same org
    existing_invite = await db.scalar(
        select(OrgInvite).where(
            OrgInvite.org_id == current_user.org_id,
            OrgInvite.email == body.email,
            OrgInvite.accepted_at.is_(None),
            OrgInvite.expires_at > datetime.now(tz=timezone.utc),
        )
    )
    if existing_invite is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A pending invite for {body.email} already exists. Cancel it first or wait for it to expire.",
        )

    token = secrets.token_urlsafe(48)
    expires_at = datetime.now(tz=timezone.utc) + timedelta(days=7)

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


@router.delete("/org/invites/{invite_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None, summary="Cancel an invite")
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


# ── Accept invite (public) ────────────────────────────────────────────────────

_accept_router = APIRouter(prefix="/auth", tags=["auth"])


@_accept_router.post("/accept-invite", response_model=TokenResponse, status_code=status.HTTP_201_CREATED, summary="Accept an org invite and create account")
async def accept_invite(
    body: AcceptInviteRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    if len(body.password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters")

    result = await db.execute(select(OrgInvite).where(OrgInvite.token == body.token))
    invite = result.scalar_one_or_none()
    if invite is None:
        raise HTTPException(status_code=400, detail="Invalid invite token")
    if invite.accepted_at is not None:
        raise HTTPException(status_code=400, detail="Invite has already been used")
    if invite.expires_at < datetime.now(tz=timezone.utc):
        raise HTTPException(status_code=400, detail="Invite has expired")

    # Check email not already registered
    existing = await db.execute(select(User).where(User.email == invite.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    hashed = _sec.hash_password(body.password)
    user = User(
        org_id=invite.org_id,
        email=invite.email,
        display_name=body.display_name,
        hashed_password=hashed,
        role=invite.role,
        is_active=True,
        is_verified=True,  # invited users are pre-verified via email
    )
    db.add(user)

    invite.accepted_at = datetime.now(tz=timezone.utc)

    await db.commit()
    await db.refresh(user)

    access_token, refresh_token = await auth_service.create_token_pair(db=db, user=user)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )
