from __future__ import annotations

from uuid import UUID

from alama_common.ids import new_uuid7
from alama_common.pagination import decode_cursor, encode_cursor

from repository_service.domain.models import (
    Installation,
    RepositoryConnection,
    RepoSnapshot,
    ScmProviderName,
    WebhookDelivery,
)


class InMemoryOutbox:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    async def enqueue(
        self,
        *,
        aggregate_type: str,
        aggregate_id: UUID,
        event_type: str,
        payload: dict[str, object],
    ) -> None:
        self.events.append(
            {
                "id": str(new_uuid7()),
                "aggregate_type": aggregate_type,
                "aggregate_id": str(aggregate_id),
                "event_type": event_type,
                "payload": payload,
            }
        )


class InMemoryRepositoryStore:
    def __init__(self) -> None:
        self.installations: dict[UUID, Installation] = {}
        self.repositories: dict[UUID, RepositoryConnection] = {}
        self.webhooks: dict[UUID, WebhookDelivery] = {}
        self.snapshots: dict[UUID, RepoSnapshot] = {}
        self.outbox = InMemoryOutbox()


class InMemoryInstallationRepository:
    def __init__(self, store: InMemoryRepositoryStore) -> None:
        self._store = store

    async def get_by_id(self, installation_id: UUID) -> Installation | None:
        return self._store.installations.get(installation_id)

    async def get_by_external(
        self,
        tenant_id: UUID,
        provider: ScmProviderName,
        external_installation_id: str,
    ) -> Installation | None:
        for item in self._store.installations.values():
            if (
                item.tenant_id == tenant_id
                and item.provider == provider
                and item.external_installation_id == external_installation_id
            ):
                return item
        return None

    async def save(self, installation: Installation) -> None:
        self._store.installations[installation.id] = installation


class InMemoryRepositoryRepository:
    def __init__(self, store: InMemoryRepositoryStore) -> None:
        self._store = store

    async def get_by_id(self, repository_id: UUID) -> RepositoryConnection | None:
        return self._store.repositories.get(repository_id)

    async def get_by_external(
        self,
        tenant_id: UUID,
        provider: ScmProviderName,
        external_repo_id: str,
    ) -> RepositoryConnection | None:
        for item in self._store.repositories.values():
            if (
                item.tenant_id == tenant_id
                and item.provider == provider
                and item.external_repo_id == external_repo_id
                and item.deleted_at is None
            ):
                return item
        return None

    async def list_by_tenant(
        self,
        tenant_id: UUID,
        *,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[RepositoryConnection], str | None]:
        items = sorted(
            [
                r
                for r in self._store.repositories.values()
                if r.tenant_id == tenant_id and r.deleted_at is None
            ],
            key=lambda r: r.created_at,
        )
        start = 0
        if cursor:
            cursor_id = str(decode_cursor(cursor)["id"])
            for idx, item in enumerate(items):
                if str(item.id) == cursor_id:
                    start = idx + 1
                    break
        page = items[start : start + limit]
        next_cursor = None
        if start + limit < len(items):
            next_cursor = encode_cursor({"id": str(page[-1].id)})
        return page, next_cursor

    async def save(self, repository: RepositoryConnection) -> None:
        self._store.repositories[repository.id] = repository


class InMemoryWebhookDeliveryRepository:
    def __init__(self, store: InMemoryRepositoryStore) -> None:
        self._store = store

    async def get_by_delivery(
        self,
        provider: ScmProviderName,
        delivery_id: str,
    ) -> WebhookDelivery | None:
        for item in self._store.webhooks.values():
            if item.provider == provider and item.delivery_id == delivery_id:
                return item
        return None

    async def save(self, delivery: WebhookDelivery) -> None:
        self._store.webhooks[delivery.id] = delivery


class InMemorySnapshotRepository:
    def __init__(self, store: InMemoryRepositoryStore) -> None:
        self._store = store

    async def get_by_id(self, snapshot_id: UUID) -> RepoSnapshot | None:
        return self._store.snapshots.get(snapshot_id)

    async def get_by_commit(self, repository_id: UUID, commit_sha: str) -> RepoSnapshot | None:
        sha = commit_sha.lower()
        for item in self._store.snapshots.values():
            if item.repository_id == repository_id and item.commit_sha == sha:
                return item
        return None

    async def list_by_repository(
        self,
        repository_id: UUID,
        *,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[RepoSnapshot], str | None]:
        items = sorted(
            [s for s in self._store.snapshots.values() if s.repository_id == repository_id],
            key=lambda s: s.created_at,
            reverse=True,
        )
        start = 0
        if cursor:
            cursor_id = str(decode_cursor(cursor)["id"])
            for idx, item in enumerate(items):
                if str(item.id) == cursor_id:
                    start = idx + 1
                    break
        page = items[start : start + limit]
        next_cursor = None
        if start + limit < len(items):
            next_cursor = encode_cursor({"id": str(page[-1].id)})
        return page, next_cursor

    async def latest_for_repository(self, repository_id: UUID) -> RepoSnapshot | None:
        items, _ = await self.list_by_repository(repository_id, limit=1, cursor=None)
        return items[0] if items else None

    async def save(self, snapshot: RepoSnapshot) -> None:
        self._store.snapshots[snapshot.id] = snapshot
