# Copyright (c) 2026 Jaiden Sy. All rights reserved.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Arbiter — SQLAlchemy ORM model: CliDeviceCode.

Stores pending and completed device-flow authorization requests issued when
a CLI client calls POST /api/v1/auth/cli/device.  The user_code is shown in
the terminal; the device_code is polled by the CLI; both expire after 15 minutes.

Status transitions:
    pending   → approved (user authorized via dashboard)
    pending   → rejected (user denied via dashboard)
    pending   → expired  (eviction loop or poll endpoint sets this on TTL breach)
    approved  → consumed (poll endpoint issues JWT and closes the record)
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CliDeviceCode(Base):
    """
    Tracks a single device-flow authorization attempt.

    Columns:
        id:          Auto-generated UUID primary key.
        device_code: UUID-formatted string — sent to CLI, used to poll /token.
        user_code:   Short human-readable code (WORD-NNNN) shown in the terminal.
        user_id:     FK → users.id; null until the user approves.
        org_id:      FK → organizations.id; null until the user approves.
        status:      Lifecycle state — "pending" | "approved" | "rejected" |
                     "expired" | "consumed".
        expires_at:  UTC timestamp when this record becomes invalid (now + 900s).
        created_at:  Immutable insert timestamp.
        approved_at: UTC timestamp when the user approved; null otherwise.
    """

    __tablename__ = "cli_device_codes"
    __table_args__ = (Index("ix_cli_device_codes_status_expires_at", "status", "expires_at"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    device_code: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        unique=True,
        index=True,
    )
    user_code: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        unique=True,
        index=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    )
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending",
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<CliDeviceCode id={self.id} user_code={self.user_code!r} status={self.status!r}>"
