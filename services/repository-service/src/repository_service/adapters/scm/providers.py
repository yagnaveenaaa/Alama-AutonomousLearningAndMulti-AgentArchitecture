from __future__ import annotations

import hashlib
import hmac

from repository_service.domain.models import (
    RepoVisibility,
    ScmProviderName,
    SecretRef,
    SizeTier,
)
from repository_service.domain.scm import ScmPermissionProjection, ScmRepoInfo


class _FakeScmCatalog:
    """Deterministic in-process SCM catalog for local/dev and tests.

    Production adapters replace this with live provider HTTP clients while
    keeping SecretRef-only credential access.
    """

    def __init__(self) -> None:
        self.repos: dict[tuple[str, str, str], ScmRepoInfo] = {}
        self.webhook_secrets: dict[str, str] = {}
        self.ref_commits: dict[tuple[str, str, str, str], str] = {}

    def seed_repo(
        self,
        *,
        provider: str,
        installation_external_id: str,
        external_repo_id: str,
        full_name: str,
        default_branch: str = "main",
        visibility: RepoVisibility = RepoVisibility.PRIVATE,
        default_commit_sha: str | None = None,
        webhook_secret: str = "test-webhook-secret",
    ) -> ScmRepoInfo:
        sha = default_commit_sha or ("a" * 40)
        info = ScmRepoInfo(
            external_repo_id=external_repo_id,
            full_name=full_name,
            default_branch=default_branch,
            visibility=visibility,
            default_commit_sha=sha,
            size_tier=SizeTier.HOT,
        )
        self.repos[(provider, installation_external_id, external_repo_id)] = info
        self.webhook_secrets[f"{provider}:{installation_external_id}"] = webhook_secret
        self.ref_commits[(provider, installation_external_id, external_repo_id, default_branch)] = (
            sha
        )
        return info


SHARED_SCM_CATALOG = _FakeScmCatalog()


class _BaseScmAdapter:
    name: ScmProviderName

    def __init__(self, catalog: _FakeScmCatalog | None = None) -> None:
        self._catalog = catalog or SHARED_SCM_CATALOG

    async def resolve_repository(
        self,
        *,
        installation_external_id: str,
        external_repo_id: str,
        secret_ref: SecretRef,
    ) -> ScmRepoInfo:
        _ = secret_ref  # production: fetch token via secret manager using path
        key = (self.name.value, installation_external_id, external_repo_id)
        info = self._catalog.repos.get(key)
        if info is None:
            from alama_common.errors import NotFoundError

            raise NotFoundError("SCM repository not found for installation")
        return info

    async def resolve_ref_commit(
        self,
        *,
        installation_external_id: str,
        external_repo_id: str,
        ref: str,
        secret_ref: SecretRef,
    ) -> str:
        _ = secret_ref
        key = (self.name.value, installation_external_id, external_repo_id, ref)
        sha = self._catalog.ref_commits.get(key)
        if sha is None:
            # Fall back to default commit if ref unknown in catalog
            repo = await self.resolve_repository(
                installation_external_id=installation_external_id,
                external_repo_id=external_repo_id,
                secret_ref=SecretRef("unused"),
            )
            return repo.default_commit_sha
        return sha

    async def refresh_permissions(
        self,
        *,
        installation_external_id: str,
        external_repo_id: str,
        secret_ref: SecretRef,
        subject_external_id: str,
    ) -> ScmPermissionProjection:
        _ = (installation_external_id, external_repo_id, secret_ref, subject_external_id)
        return ScmPermissionProjection(can_read=True, can_write=True, can_admin=False)

    def verify_webhook_signature(
        self,
        *,
        body: bytes,
        signature_header: str | None,
        secret_ref: SecretRef,
    ) -> bool:
        # secret_ref.path encodes lookup key provider:installation for local catalog
        secret = self._catalog.webhook_secrets.get(secret_ref.path)
        if secret is None or signature_header is None:
            return False
        digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        expected = f"sha256={digest}"
        return hmac.compare_digest(expected, signature_header)


class GithubScmAdapter(_BaseScmAdapter):
    name = ScmProviderName.GITHUB


class GitlabScmAdapter(_BaseScmAdapter):
    name = ScmProviderName.GITLAB


class BitbucketScmAdapter(_BaseScmAdapter):
    name = ScmProviderName.BITBUCKET
