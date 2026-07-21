from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from usage_service.domain.models import BudgetPeriod, UsageCategory, UsageUnit


@dataclass(frozen=True, slots=True)
class IngestUsageCommand:
    tenant_id: UUID
    category: UsageCategory
    quantity: int
    unit: UsageUnit
    price_version: str
    provider: str
    idempotency_key: str
    task_id: UUID | None = None
    model: str | None = None
    enforce_budget: bool = True


@dataclass(frozen=True, slots=True)
class ReserveBudgetCommand:
    tenant_id: UUID
    tokens: int = 0
    usd_micros: int = 0
    period: BudgetPeriod = BudgetPeriod.MONTHLY


@dataclass(frozen=True, slots=True)
class CommitBudgetCommand:
    tenant_id: UUID
    tokens: int = 0
    usd_micros: int = 0
    period: BudgetPeriod = BudgetPeriod.MONTHLY


@dataclass(frozen=True, slots=True)
class UpsertBudgetCommand:
    tenant_id: UUID
    period: BudgetPeriod
    limit_usd_micros: int
    limit_tokens: int
    soft_pct: float = 0.8
    hard_stop: bool = True
