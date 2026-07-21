from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from usage_service.domain.models import AnomalyFlag, Budget, BudgetPeriod, UsageRecord


class UsageLedgerRepository(Protocol):
    async def get_by_idempotency_key(
        self, tenant_id: UUID, idempotency_key: str
    ) -> UsageRecord | None: ...

    async def append(self, record: UsageRecord) -> None: ...

    async def list_for_tenant(
        self,
        tenant_id: UUID,
        *,
        since: datetime | None,
        until: datetime | None,
    ) -> list[UsageRecord]: ...


class BudgetRepository(Protocol):
    async def get_current(
        self, tenant_id: UUID, period: BudgetPeriod
    ) -> Budget | None: ...

    async def save(self, budget: Budget) -> None: ...

    async def list_for_tenant(self, tenant_id: UUID) -> list[Budget]: ...


class AnomalyRepository(Protocol):
    async def save(self, flag: AnomalyFlag) -> None: ...

    async def list_for_tenant(self, tenant_id: UUID) -> list[AnomalyFlag]: ...
