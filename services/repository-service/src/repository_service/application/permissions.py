from __future__ import annotations

from uuid import UUID

from alama_common.errors import NotFoundError

from repository_service.domain.repositories import InstallationRepository, RepositoryRepository
from repository_service.domain.scm import ScmPermissionProjection, ScmProvider


class PermissionRefreshService:
    """Refresh SCM ACL cache projection (LLD §2.4)."""

    def __init__(
        self,
        repositories: RepositoryRepository,
        installations: InstallationRepository,
        providers: dict[str, ScmProvider],
        cache: dict[tuple[UUID, str], ScmPermissionProjection],
    ) -> None:
        self._repositories = repositories
        self._installations = installations
        self._providers = providers
        self._cache = cache

    async def refresh(
        self,
        *,
        tenant_id: UUID,
        repository_id: UUID,
        subject_external_id: str,
    ) -> ScmPermissionProjection:
        repo = await self._repositories.get_by_id(repository_id)
        if repo is None or repo.tenant_id != tenant_id or repo.deleted_at is not None:
            raise NotFoundError("Repository not found")
        installation = await self._installations.get_by_id(repo.installation_id)
        if installation is None:
            raise NotFoundError("Installation not found")
        provider = self._providers[repo.provider.value]
        projection = await provider.refresh_permissions(
            installation_external_id=installation.external_installation_id,
            external_repo_id=repo.external_repo_id,
            secret_ref=installation.secret_ref,
            subject_external_id=subject_external_id,
        )
        self._cache[(repository_id, subject_external_id)] = projection
        return projection
