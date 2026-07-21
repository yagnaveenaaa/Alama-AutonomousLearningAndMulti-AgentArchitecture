from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class NotificationRow(Base):
    """notification.notifications (LLD §4.8)."""

    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "idempotency_key", name="uq_notifications_idempotency"
        ),
        Index("ix_notifications_recipient_created", "tenant_id", "recipient_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    recipient_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    template_key: Mapped[str] = mapped_column(String(128), nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempt_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)


class DeliveryAttemptRow(Base):
    """notification.delivery_attempts."""

    __tablename__ = "delivery_attempts"
    __table_args__ = (
        Index("ix_delivery_attempts_notification", "notification_id", "attempt_number"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    notification_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    attempt_number: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ChannelPreferenceRow(Base):
    """notification.channel_preferences."""

    __tablename__ = "channel_preferences"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "recipient_id",
            "channel",
            name="uq_channel_preferences_recipient",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    recipient_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    destination: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
