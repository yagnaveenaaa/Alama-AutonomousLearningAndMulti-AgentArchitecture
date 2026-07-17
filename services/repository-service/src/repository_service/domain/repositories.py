from __future__ import annotations

from typing import Protocol
from uuid import UUID

from repository_service.domain.models import (
    Installation,
    RepositoryConnection,
    RepoSnapshot,
    ScmProviderName,
    WebhookDelivery,
)


class InstallationRepository(Protocol):
    async def get_by_id(self, installation_id: UUID) -> Installation | None: ...

    async def get_by_external(
        self,
        tenant_id: UUID,
        provider: ScmProviderName,
        external_installation_id: str,
    ) -> Installation | None: ...

    async def save(self, installation: Installation) -> None: ...


class RepositoryRepository(Protocol):
    async def get_by_id(self, repository_id: UUID) -> RepositoryConnection | None: ...

    async def get_by_external(
        self,
        tenant_id: UUID,
        provider: ScmProviderName,
        external_repo_id: str,
    ) -> RepositoryConnection | None: ...

    async def list_by_tenant(
        self,
        tenant_id: UUID,
        *,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[RepositoryConnection], str | None]: ...

    async def save(self, repository: RepositoryConnection) -> None: ...


class WebhookDeliveryRepository(Protocol):
    async def get_by_delivery(
        self,
        provider: ScmProviderName,
        delivery_id: str,
    ) -> WebhookDelivery | None: ...

    async def save(self, delivery: WebhookDelivery) -> None: ...


class SnapshotRepository(Protocol):
    async def get_by_id(self, snapshot_id: UUID) -> RepoSnapshot | None: ...

    async def get_by_commit(
        self,
        repository_id: UUID,
        commit_sha: str,
    ) -> RepoSnapshot | None: ...

    async def list_by_repository(
        self,
        repository_id: UUID,
        *,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[RepoSnapshot], str | None]: ...

    async def latest_for_repository(self, repository_id: UUID) -> RepoSnapshot | None: ...

    async def save(self, snapshot: RepoSnapshot) -> None: ...


class OutboxRepository(Protocol):
    async def enqueue(
        self,
        *,
        aggregate_type: str,
        aggregate_id: UUID,
        event_type: str,
        payload: dict[str, object],
    ) -> None: ...
