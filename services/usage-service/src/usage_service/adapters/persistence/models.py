from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class UsageLedgerRow(Base):
    """usage.usage_ledger (LLD §4.8)."""

    __tablename__ = "usage_ledger"
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_usage_ledger_idempotency"),
        Index("ix_usage_ledger_tenant_created", "tenant_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    task_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    quantity: Mapped[int] = mapped_column(BigInteger, nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    price_version: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class BudgetRow(Base):
    """usage.budgets (LLD §4.8)."""

    __tablename__ = "budgets"
    __table_args__ = (
        UniqueConstraint("tenant_id", "period", name="uq_budgets_tenant_period"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    period: Mapped[str] = mapped_column(String(32), nullable=False)
    limit_usd_micros: Mapped[int] = mapped_column(BigInteger, nullable=False)
    limit_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False)
    soft_pct: Mapped[float] = mapped_column(Float, nullable=False)
    hard_stop: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    spent_usd_micros: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    spent_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    reserved_usd_micros: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    reserved_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
