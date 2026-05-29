"""
Arbiter — Pydantic schemas for the auth endpoints.

All request/response bodies for /auth/* routes are defined here.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    """Body for POST /auth/register."""

    org_name: str = Field(..., max_length=255)
    email: EmailStr
    password: str
    invite_code: str = ""

    @field_validator("org_name")
    @classmethod
    def org_name_not_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("org_name must not be blank")
        return value.strip()

    @field_validator("password")
    @classmethod
    def password_min_length(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters")
        return value


class LoginRequest(BaseModel):
    """Body for POST /auth/login."""

    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    """Body for POST /auth/refresh."""

    refresh_token: str


class TokenResponse(BaseModel):
    """Shared response shape for register, login, and refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds until access token expires


class MeResponse(BaseModel):
    """Response for GET /auth/me and PATCH /auth/me."""

    id: uuid.UUID
    email: str
    display_name: str | None
    role: str
    org_id: uuid.UUID
    org_name: str
    org_plan: str
    has_password: bool
    linked_providers: list[str]
    avatar_url: str | None
    is_verified: bool

    model_config = {"from_attributes": True}


class UpdateMeRequest(BaseModel):
    """Body for PATCH /auth/me."""

    display_name: str | None = None
    email: EmailStr | None = None

    @field_validator("display_name")
    @classmethod
    def display_name_length(cls, value: str | None) -> str | None:
        if value is not None and len(value.strip()) == 0:
            raise ValueError("display_name must not be blank")
        if value is not None and len(value) > 64:
            raise ValueError("display_name must be 64 characters or fewer")
        return value.strip() if value else value


class ChangePasswordRequest(BaseModel):
    """Body for POST /auth/me/change-password."""

    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def new_password_min_length(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters")
        return value
