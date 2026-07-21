from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Index, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class PolicyBundleRow(Base):
    """policy.policy_bundles (LLD §4.8)."""

    __tablename__ = "policy_bundles"
    __table_args__ = (
        UniqueConstraint("tenant_id", "version", name="uq_policy_bundles_tenant_version"),
        Index(
            "uq_policy_bundles_one_active",
            "tenant_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        Index("ix_policy_bundles_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    version: Mapped[str] = mapped_column(Text, nullable=False)
    bundle_ref: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    checksum: Mapped[str] = mapped_column(Text, nullable=False)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
