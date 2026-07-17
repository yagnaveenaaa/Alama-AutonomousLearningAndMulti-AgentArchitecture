from __future__ import annotations

from alama_common.errors import ConflictError, NotFoundError, ValidationError
from alama_common.ids import new_uuid7

from repository_service.application.dto import ReindexCommand
from repository_service.domain.models import RepoSnapshot
from repository_service.domain.repositories import (
    InstallationRepository,
    OutboxRepository,
    RepositoryRepository,
    SnapshotRepository,
)
from repository_service.domain.scm import ScmProvider


class SnapshotRequestService:
    """Enqueue indexing snapshot intents (LLD §2.4)."""

    def __init__(
        self,
        repositories: RepositoryRepository,
        installations: InstallationRepository,
        snapshots: SnapshotRepository,
        outbox: OutboxRepository,
        providers: dict[str, ScmProvider],
    ) -> None:
        self._repositories = repositories
        self._installations = installations
        self._snapshots = snapshots
        self._outbox = outbox
        self._providers = providers

    async def request_reindex(self, command: ReindexCommand) -> RepoSnapshot:
        repo = await self._repositories.get_by_id(command.repository_id)
        if repo is None or repo.tenant_id != command.tenant_id or repo.deleted_at is not None:
            raise NotFoundError("Repository not found")

        installation = await self._installations.get_by_id(repo.installation_id)
        if installation is None:
            raise NotFoundError("Installation not found")

        provider = self._providers.get(repo.provider.value)
        if provider is None:
            raise ValidationError(f"Unsupported provider: {repo.provider.value}")

        ref = command.ref or repo.default_branch
        commit_sha = await provider.resolve_ref_commit(
            installation_external_id=installation.external_installation_id,
            external_repo_id=repo.external_repo_id,
            ref=ref,
            secret_ref=installation.secret_ref,
        )

        existing = await self._snapshots.get_by_commit(repo.id, commit_sha)
        if existing is not None:
            raise ConflictError(
                "Snapshot already exists for commit",
                details={"snapshot_id": str(existing.id), "commit_sha": commit_sha},
            )

        snapshot = RepoSnapshot.request(
            tenant_id=command.tenant_id,
            repository_id=repo.id,
            commit_sha=commit_sha,
        )
        await self._snapshots.save(snapshot)
        await self._outbox.enqueue(
            aggregate_type="repo_snapshot",
            aggregate_id=snapshot.id,
            event_type="com.alama.repository.snapshot.requested.v1",
            payload={
                "snapshot_id": str(snapshot.id),
                "repository_id": str(repo.id),
                "tenant_id": str(command.tenant_id),
                "commit_sha": commit_sha,
                "request_id": str(new_uuid7()),
            },
        )
        repo.mark_synced()
        await self._repositories.save(repo)
        return snapshot
