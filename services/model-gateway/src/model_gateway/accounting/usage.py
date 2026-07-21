from __future__ import annotations

from uuid import UUID

from alama_common.errors import BudgetExceededError

from model_gateway.domain.models import UsageRecord


class InMemoryUsageEmitter:
    """Kafka-class usage ledger stand-in (LLD §2.9 accounting)."""

    def __init__(self) -> None:
        self.records: list[UsageRecord] = []

    async def emit(self, record: UsageRecord) -> None:
        self.records.append(record)


class InMemoryQuotaService:
    def __init__(self, *, tenant_token_quota: int) -> None:
        self._quota = tenant_token_quota
        self._spent: dict[UUID, int] = {}

    async def consume(self, tenant_id: UUID, tokens: int) -> None:
        spent = self._spent.get(tenant_id, 0) + tokens
        if spent > self._quota:
            raise BudgetExceededError(
                "Tenant model token quota exceeded",
                details={"spent": spent, "quota": self._quota},
            )
        self._spent[tenant_id] = spent

    def remaining(self, tenant_id: UUID) -> int:
        return self._quota - self._spent.get(tenant_id, 0)
