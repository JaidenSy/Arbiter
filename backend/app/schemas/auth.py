"""
NexusAI — Pydantic schemas for the auth endpoints.

All request/response bodies for /auth/* routes are defined here.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, EmailStr, field_validator


class RegisterRequest(BaseModel):
    """Body for POST /auth/register."""

    org_name: str
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
    """Response for GET /auth/me."""

    id: uuid.UUID
    email: str
    role: str
    org_id: uuid.UUID
    org_name: str
    org_plan: str

    model_config = {"from_attributes": True}
