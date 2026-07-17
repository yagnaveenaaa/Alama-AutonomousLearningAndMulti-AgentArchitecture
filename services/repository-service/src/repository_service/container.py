from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from repository_service.adapters.persistence.memory import (
    InMemoryInstallationRepository,
    InMemoryRepositoryRepository,
    InMemoryRepositoryStore,
    InMemorySnapshotRepository,
    InMemoryWebhookDeliveryRepository,
)
from repository_service.adapters.scm import (
    BitbucketScmAdapter,
    GithubScmAdapter,
    GitlabScmAdapter,
)
from repository_service.application.connect import ConnectRepositoryHandler
from repository_service.application.permissions import PermissionRefreshService
from repository_service.application.snapshots import SnapshotRequestService
from repository_service.application.webhooks import WebhookIngestor
from repository_service.domain.scm import ScmPermissionProjection, ScmProvider


@dataclass
class RepositoryContainer:
    store: InMemoryRepositoryStore
    installations: InMemoryInstallationRepository
    repositories: InMemoryRepositoryRepository
    webhooks: InMemoryWebhookDeliveryRepository
    snapshots: InMemorySnapshotRepository
    providers: dict[str, ScmProvider]
    connect: ConnectRepositoryHandler
    snapshots_service: SnapshotRequestService
    webhook_ingestor: WebhookIngestor
    permissions: PermissionRefreshService


def build_container() -> RepositoryContainer:
    store = InMemoryRepositoryStore()
    installations = InMemoryInstallationRepository(store)
    repositories = InMemoryRepositoryRepository(store)
    webhooks = InMemoryWebhookDeliveryRepository(store)
    snapshots = InMemorySnapshotRepository(store)
    providers: dict[str, ScmProvider] = {
        "github": GithubScmAdapter(),
        "gitlab": GitlabScmAdapter(),
        "bitbucket": BitbucketScmAdapter(),
    }
    permission_cache: dict[tuple[UUID, str], ScmPermissionProjection] = {}
    return RepositoryContainer(
        store=store,
        installations=installations,
        repositories=repositories,
        webhooks=webhooks,
        snapshots=snapshots,
        providers=providers,
        connect=ConnectRepositoryHandler(installations, repositories, providers),
        snapshots_service=SnapshotRequestService(
            repositories,
            installations,
            snapshots,
            store.outbox,
            providers,
        ),
        webhook_ingestor=WebhookIngestor(webhooks, store.outbox, providers),
        permissions=PermissionRefreshService(
            repositories,
            installations,
            providers,
            permission_cache,
        ),
    )
