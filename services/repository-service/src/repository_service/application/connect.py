from __future__ import annotations

from uuid import UUID

from alama_common.errors import ConflictError, NotFoundError, ValidationError

from repository_service.application.dto import ConnectRepositoryCommand, RegisterInstallationCommand
from repository_service.domain.models import (
    Installation,
    InstallationStatus,
    RepositoryConnection,
    SecretRef,
)
from repository_service.domain.repositories import InstallationRepository, RepositoryRepository
from repository_service.domain.scm import ScmProvider


class ConnectRepositoryHandler:
    """Connect a repository via ScmProvider metadata (LLD §2.4 application)."""

    def __init__(
        self,
        installations: InstallationRepository,
        repositories: RepositoryRepository,
        providers: dict[str, ScmProvider],
    ) -> None:
        self._installations = installations
        self._repositories = repositories
        self._providers = providers

    async def register_installation(self, command: RegisterInstallationCommand) -> Installation:
        existing = await self._installations.get_by_external(
            command.tenant_id,
            command.provider,
            command.external_installation_id,
        )
        if existing is not None:
            raise ConflictError("Installation already registered")

        installation = Installation.create(
            tenant_id=command.tenant_id,
            provider=command.provider,
            external_installation_id=command.external_installation_id,
            account_login=command.account_login,
            secret_ref=SecretRef(command.secret_ref_path),
        )
        await self._installations.save(installation)
        return installation

    async def connect(self, command: ConnectRepositoryCommand) -> RepositoryConnection:
        if not command.external_repo_id.strip():
            raise ValidationError("external_repo_id is required")

        installation = await self._installations.get_by_id(command.installation_id)
        if installation is None or installation.tenant_id != command.tenant_id:
            raise NotFoundError("Installation not found")
        if installation.provider != command.provider:
            raise ValidationError("provider does not match installation")
        if installation.status != InstallationStatus.ACTIVE:
            raise ConflictError("Installation is not active")

        existing = await self._repositories.get_by_external(
            command.tenant_id,
            command.provider,
            command.external_repo_id,
        )
        if existing is not None and existing.deleted_at is None:
            raise ConflictError("Repository already connected")

        provider = self._providers.get(command.provider.value)
        if provider is None:
            raise ValidationError(f"Unsupported provider: {command.provider.value}")

        info = await provider.resolve_repository(
            installation_external_id=installation.external_installation_id,
            external_repo_id=command.external_repo_id,
            secret_ref=installation.secret_ref,
        )

        repo = RepositoryConnection.connect(
            tenant_id=command.tenant_id,
            installation_id=installation.id,
            provider=command.provider,
            external_repo_id=info.external_repo_id,
            full_name=info.full_name,
            default_branch=info.default_branch,
            visibility=info.visibility,
            size_tier=info.size_tier,
        )
        await self._repositories.save(repo)
        return repo

    async def disconnect(self, *, tenant_id: UUID, repository_id: UUID) -> None:
        repo = await self._repositories.get_by_id(repository_id)
        if repo is None or repo.tenant_id != tenant_id or repo.deleted_at is not None:
            raise NotFoundError("Repository not found")
        repo.soft_delete()
        await self._repositories.save(repo)
