from __future__ import annotations

from datetime import datetime
from uuid import UUID

from usage_service.domain.models import (
    AnomalyFlag,
    Budget,
    BudgetPeriod,
    UsageRecord,
)


class InMemoryUsageStore:
    def __init__(self) -> None:
        self.records: list[UsageRecord] = []
        self.budgets: dict[tuple[UUID, str], Budget] = {}
        self.anomalies: list[AnomalyFlag] = []


class InMemoryUsageLedgerRepository:
    def __init__(self, store: InMemoryUsageStore) -> None:
        self._store = store

    async def get_by_idempotency_key(
        self, tenant_id: UUID, idempotency_key: str
    ) -> UsageRecord | None:
        for record in self._store.records:
            if (
                record.tenant_id == tenant_id
                and record.idempotency_key == idempotency_key
            ):
                return record
        return None

    async def append(self, record: UsageRecord) -> None:
        self._store.records.append(record)

    async def list_for_tenant(
        self,
        tenant_id: UUID,
        *,
        since: datetime | None,
        until: datetime | None,
    ) -> list[UsageRecord]:
        items = [r for r in self._store.records if r.tenant_id == tenant_id]
        if since is not None:
            items = [r for r in items if r.created_at >= since]
        if until is not None:
            items = [r for r in items if r.created_at <= until]
        items.sort(key=lambda r: r.created_at)
        return items


class InMemoryBudgetRepository:
    def __init__(self, store: InMemoryUsageStore) -> None:
        self._store = store

    async def get_current(
        self, tenant_id: UUID, period: BudgetPeriod
    ) -> Budget | None:
        return self._store.budgets.get((tenant_id, period.value))

    async def save(self, budget: Budget) -> None:
        self._store.budgets[(budget.tenant_id, budget.period.value)] = budget

    async def list_for_tenant(self, tenant_id: UUID) -> list[Budget]:
        return [b for (tid, _), b in self._store.budgets.items() if tid == tenant_id]


class InMemoryAnomalyRepository:
    def __init__(self, store: InMemoryUsageStore) -> None:
        self._store = store

    async def save(self, flag: AnomalyFlag) -> None:
        self._store.anomalies.append(flag)

    async def list_for_tenant(self, tenant_id: UUID) -> list[AnomalyFlag]:
        return [f for f in self._store.anomalies if f.tenant_id == tenant_id]
