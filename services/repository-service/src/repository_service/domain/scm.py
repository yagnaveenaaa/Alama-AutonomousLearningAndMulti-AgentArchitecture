from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from repository_service.domain.models import (
    RepoVisibility,
    ScmProviderName,
    SecretRef,
    SizeTier,
)


@dataclass(frozen=True, slots=True)
class ScmRepoInfo:
    external_repo_id: str
    full_name: str
    default_branch: str
    visibility: RepoVisibility
    default_commit_sha: str
    size_tier: SizeTier = SizeTier.HOT


@dataclass(frozen=True, slots=True)
class ScmPermissionProjection:
    can_read: bool
    can_write: bool
    can_admin: bool


class ScmProvider(Protocol):
    """Normalize provider operations (LLD §2.4)."""

    name: ScmProviderName

    async def resolve_repository(
        self,
        *,
        installation_external_id: str,
        external_repo_id: str,
        secret_ref: SecretRef,
    ) -> ScmRepoInfo: ...

    async def resolve_ref_commit(
        self,
        *,
        installation_external_id: str,
        external_repo_id: str,
        ref: str,
        secret_ref: SecretRef,
    ) -> str: ...

    async def refresh_permissions(
        self,
        *,
        installation_external_id: str,
        external_repo_id: str,
        secret_ref: SecretRef,
        subject_external_id: str,
    ) -> ScmPermissionProjection: ...

    def verify_webhook_signature(
        self,
        *,
        body: bytes,
        signature_header: str | None,
        secret_ref: SecretRef,
    ) -> bool: ...
