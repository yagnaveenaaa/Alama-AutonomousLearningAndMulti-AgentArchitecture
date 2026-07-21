from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from usage_service.domain.models import BudgetPeriod, UsageCategory, UsageUnit


class HealthResponse(BaseModel):
    status: str
    service: str


class IngestUsageRequest(BaseModel):
    category: UsageCategory
    quantity: int = Field(ge=0)
    unit: UsageUnit
    price_version: str = Field(default="price.v1", min_length=1)
    provider: str = Field(min_length=1, max_length=128)
    idempotency_key: str = Field(min_length=1, max_length=256)
    task_id: UUID | None = None
    model: str | None = None
    enforce_budget: bool = True


class UsageRecordResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    task_id: UUID | None
    category: str
    quantity: int
    unit: str
    price_version: str
    provider: str
    model: str | None
    idempotency_key: str
    created_at: datetime
    created: bool = True


class BudgetResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    period: str
    limit_usd_micros: int
    limit_tokens: int
    soft_pct: float
    hard_stop: bool
    spent_usd_micros: int
    spent_tokens: int
    reserved_usd_micros: int
    reserved_tokens: int
    soft_warning: bool
    updated_at: datetime


class BudgetListResponse(BaseModel):
    items: list[BudgetResponse]


class UpsertBudgetRequest(BaseModel):
    period: BudgetPeriod = BudgetPeriod.MONTHLY
    limit_usd_micros: int = Field(ge=0)
    limit_tokens: int = Field(ge=0)
    soft_pct: float = Field(default=0.8, ge=0.0, le=1.0)
    hard_stop: bool = True


class ReserveBudgetRequest(BaseModel):
    tokens: int = Field(default=0, ge=0)
    usd_micros: int = Field(default=0, ge=0)
    period: BudgetPeriod = BudgetPeriod.MONTHLY


class AnomalyResponse(BaseModel):
    category: str
    ratio: float
    baseline: float
    current: float
    detected_at: datetime
    message: str


class UsageSummaryResponse(BaseModel):
    tenant_id: UUID
    period: str
    tokens_used: int
    tokens_budget: int
    usd_micros_used: int
    usd_micros_budget: int
    soft_warning: bool
    by_category: dict[str, int]
    anomalies: list[AnomalyResponse]
