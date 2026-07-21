from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from alama_common.errors import BudgetExceededError, ConflictError, ValidationError
from alama_common.ids import new_uuid7


class UsageCategory(StrEnum):
    MODEL_TOKENS = "model_tokens"
    MODEL_USD = "model_usd"
    EMBEDDING_TOKENS = "embedding_tokens"
    TOOL_CALLS = "tool_calls"
    INDEXING = "indexing"
    STORAGE = "storage"


class UsageUnit(StrEnum):
    TOKENS = "tokens"
    USD_MICROS = "usd_micros"
    CALLS = "calls"
    BYTES = "bytes"


class BudgetPeriod(StrEnum):
    MONTHLY = "monthly"
    DAILY = "daily"


@dataclass(frozen=True, slots=True)
class UsageRecord:
    """usage.usage_ledger row (LLD §4.8)."""

    id: UUID
    tenant_id: UUID
    task_id: UUID | None
    category: UsageCategory
    quantity: int
    unit: UsageUnit
    price_version: str
    provider: str
    model: str | None
    idempotency_key: str
    created_at: datetime

    @classmethod
    def create(
        cls,
        *,
        tenant_id: UUID,
        category: UsageCategory,
        quantity: int,
        unit: UsageUnit,
        price_version: str,
        provider: str,
        idempotency_key: str,
        task_id: UUID | None = None,
        model: str | None = None,
    ) -> UsageRecord:
        if quantity < 0:
            raise ValidationError("quantity must be >= 0")
        if not idempotency_key.strip():
            raise ValidationError("idempotency_key is required")
        return cls(
            id=new_uuid7(),
            tenant_id=tenant_id,
            task_id=task_id,
            category=category,
            quantity=quantity,
            unit=unit,
            price_version=price_version,
            provider=provider,
            model=model,
            idempotency_key=idempotency_key.strip(),
            created_at=datetime.now(UTC),
        )


@dataclass
class Budget:
    """usage.budgets (LLD §4.8)."""

    id: UUID
    tenant_id: UUID
    period: BudgetPeriod
    limit_usd_micros: int
    limit_tokens: int
    soft_pct: float
    hard_stop: bool
    spent_usd_micros: int
    spent_tokens: int
    reserved_usd_micros: int
    reserved_tokens: int
    updated_at: datetime

    @classmethod
    def create(
        cls,
        *,
        tenant_id: UUID,
        period: BudgetPeriod = BudgetPeriod.MONTHLY,
        limit_usd_micros: int,
        limit_tokens: int,
        soft_pct: float = 0.8,
        hard_stop: bool = True,
    ) -> Budget:
        return cls(
            id=new_uuid7(),
            tenant_id=tenant_id,
            period=period,
            limit_usd_micros=limit_usd_micros,
            limit_tokens=limit_tokens,
            soft_pct=soft_pct,
            hard_stop=hard_stop,
            spent_usd_micros=0,
            spent_tokens=0,
            reserved_usd_micros=0,
            reserved_tokens=0,
            updated_at=datetime.now(UTC),
        )

    @property
    def tokens_soft_limit(self) -> int:
        return int(self.limit_tokens * self.soft_pct)

    @property
    def usd_soft_limit(self) -> int:
        return int(self.limit_usd_micros * self.soft_pct)

    def projected_tokens(self) -> int:
        return self.spent_tokens + self.reserved_tokens

    def projected_usd(self) -> int:
        return self.spent_usd_micros + self.reserved_usd_micros

    def soft_warning(self) -> bool:
        return (
            self.projected_tokens() >= self.tokens_soft_limit
            or self.projected_usd() >= self.usd_soft_limit
        )

    def reserve(self, *, tokens: int = 0, usd_micros: int = 0) -> None:
        next_tokens = self.projected_tokens() + tokens
        next_usd = self.projected_usd() + usd_micros
        if self.hard_stop and (
            next_tokens > self.limit_tokens or next_usd > self.limit_usd_micros
        ):
            raise BudgetExceededError(
                "Budget hard stop would be exceeded",
                details={
                    "projected_tokens": next_tokens,
                    "limit_tokens": self.limit_tokens,
                    "projected_usd_micros": next_usd,
                    "limit_usd_micros": self.limit_usd_micros,
                },
            )
        self.reserved_tokens += tokens
        self.reserved_usd_micros += usd_micros
        self.updated_at = datetime.now(UTC)

    def commit(self, *, tokens: int = 0, usd_micros: int = 0) -> None:
        if tokens > self.reserved_tokens or usd_micros > self.reserved_usd_micros:
            raise ConflictError("Cannot commit more than reserved")
        self.reserved_tokens -= tokens
        self.reserved_usd_micros -= usd_micros
        self.spent_tokens += tokens
        self.spent_usd_micros += usd_micros
        if self.hard_stop and (
            self.spent_tokens > self.limit_tokens
            or self.spent_usd_micros > self.limit_usd_micros
        ):
            raise BudgetExceededError(
                "Budget hard stop exceeded on commit",
                details={
                    "spent_tokens": self.spent_tokens,
                    "limit_tokens": self.limit_tokens,
                },
            )
        self.updated_at = datetime.now(UTC)

    def release_reservation(self, *, tokens: int = 0, usd_micros: int = 0) -> None:
        self.reserved_tokens = max(0, self.reserved_tokens - tokens)
        self.reserved_usd_micros = max(0, self.reserved_usd_micros - usd_micros)
        self.updated_at = datetime.now(UTC)

    def apply_direct(self, *, tokens: int = 0, usd_micros: int = 0) -> None:
        """Commit usage without prior reservation (ingest path)."""
        next_tokens = self.spent_tokens + tokens
        next_usd = self.spent_usd_micros + usd_micros
        if self.hard_stop and (
            next_tokens > self.limit_tokens or next_usd > self.limit_usd_micros
        ):
            raise BudgetExceededError(
                "Budget hard stop exceeded",
                details={
                    "spent_tokens": next_tokens,
                    "limit_tokens": self.limit_tokens,
                    "spent_usd_micros": next_usd,
                    "limit_usd_micros": self.limit_usd_micros,
                },
            )
        self.spent_tokens = next_tokens
        self.spent_usd_micros = next_usd
        self.updated_at = datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class AnomalyFlag:
    tenant_id: UUID
    category: UsageCategory
    ratio: float
    baseline: float
    current: float
    detected_at: datetime
    message: str


@dataclass(frozen=True, slots=True)
class UsageSummary:
    tenant_id: UUID
    period: str
    tokens_used: int
    tokens_budget: int
    usd_micros_used: int
    usd_micros_budget: int
    soft_warning: bool
    by_category: dict[str, int]
    anomalies: tuple[AnomalyFlag, ...]
