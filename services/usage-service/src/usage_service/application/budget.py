from __future__ import annotations

from uuid import UUID

from usage_service.application.dto import (
    CommitBudgetCommand,
    ReserveBudgetCommand,
    UpsertBudgetCommand,
)
from usage_service.domain.models import Budget, BudgetPeriod
from usage_service.domain.repositories import BudgetRepository


class BudgetService:
    """Check / reserve / commit budget (LLD §2.12)."""

    def __init__(
        self,
        budgets: BudgetRepository,
        *,
        default_limit_tokens: int,
        default_limit_usd_micros: int,
        default_soft_pct: float,
    ) -> None:
        self._budgets = budgets
        self._default_limit_tokens = default_limit_tokens
        self._default_limit_usd = default_limit_usd_micros
        self._default_soft_pct = default_soft_pct

    async def ensure_budget(
        self, tenant_id: UUID, period: BudgetPeriod = BudgetPeriod.MONTHLY
    ) -> Budget:
        budget = await self._budgets.get_current(tenant_id, period)
        if budget is not None:
            return budget
        budget = Budget.create(
            tenant_id=tenant_id,
            period=period,
            limit_usd_micros=self._default_limit_usd,
            limit_tokens=self._default_limit_tokens,
            soft_pct=self._default_soft_pct,
            hard_stop=True,
        )
        await self._budgets.save(budget)
        return budget

    async def upsert(self, command: UpsertBudgetCommand) -> Budget:
        existing = await self._budgets.get_current(command.tenant_id, command.period)
        if existing is None:
            budget = Budget.create(
                tenant_id=command.tenant_id,
                period=command.period,
                limit_usd_micros=command.limit_usd_micros,
                limit_tokens=command.limit_tokens,
                soft_pct=command.soft_pct,
                hard_stop=command.hard_stop,
            )
        else:
            existing.limit_usd_micros = command.limit_usd_micros
            existing.limit_tokens = command.limit_tokens
            existing.soft_pct = command.soft_pct
            existing.hard_stop = command.hard_stop
            budget = existing
        await self._budgets.save(budget)
        return budget

    async def reserve(self, command: ReserveBudgetCommand) -> Budget:
        budget = await self.ensure_budget(command.tenant_id, command.period)
        budget.reserve(tokens=command.tokens, usd_micros=command.usd_micros)
        await self._budgets.save(budget)
        return budget

    async def commit(self, command: CommitBudgetCommand) -> Budget:
        budget = await self.ensure_budget(command.tenant_id, command.period)
        budget.commit(tokens=command.tokens, usd_micros=command.usd_micros)
        await self._budgets.save(budget)
        return budget

    async def apply_usage(
        self, tenant_id: UUID, *, tokens: int = 0, usd_micros: int = 0
    ) -> Budget:
        budget = await self.ensure_budget(tenant_id)
        budget.apply_direct(tokens=tokens, usd_micros=usd_micros)
        await self._budgets.save(budget)
        return budget

    async def list_budgets(self, tenant_id: UUID) -> list[Budget]:
        await self.ensure_budget(tenant_id)
        return await self._budgets.list_for_tenant(tenant_id)
