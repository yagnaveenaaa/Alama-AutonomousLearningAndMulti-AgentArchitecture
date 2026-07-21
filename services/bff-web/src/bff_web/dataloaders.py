from __future__ import annotations

from uuid import UUID

from bff_web.auth_context import AuthContext
from bff_web.clients.ports import ApprovalDto, RepoDto, ServiceClients, TaskDto, TaskEventDto


class DataLoaders:
    """Batch N+1 prevention for nested GraphQL fields (LLD §2.2)."""

    def __init__(self, clients: ServiceClients, ctx: AuthContext) -> None:
        self._clients = clients
        self._ctx = ctx
        self._task_cache: dict[UUID, TaskDto | None] = {}
        self._events_cache: dict[UUID, list[TaskEventDto]] = {}
        self._approvals_cache: dict[UUID, list[ApprovalDto]] = {}
        self._repos: list[RepoDto] | None = None

    async def task(self, task_id: UUID) -> TaskDto | None:
        if task_id not in self._task_cache:
            self._task_cache[task_id] = await self._clients.tasks.get_task(
                self._ctx, task_id
            )
        return self._task_cache[task_id]

    async def events(self, task_id: UUID) -> list[TaskEventDto]:
        if task_id not in self._events_cache:
            self._events_cache[task_id] = await self._clients.tasks.list_events(
                self._ctx, task_id
            )
        return self._events_cache[task_id]

    async def approvals(self, task_id: UUID) -> list[ApprovalDto]:
        if task_id not in self._approvals_cache:
            self._approvals_cache[task_id] = await self._clients.tasks.list_approvals(
                self._ctx, task_id
            )
        return self._approvals_cache[task_id]

    async def repos(self) -> list[RepoDto]:
        if self._repos is None:
            self._repos = await self._clients.repositories.list_repos(self._ctx)
        return self._repos
