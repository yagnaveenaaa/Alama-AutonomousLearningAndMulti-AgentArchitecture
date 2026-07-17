from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from alama_common.errors import ConflictError, DomainInvariantError, ValidationError
from alama_common.ids import new_uuid7


class ScmProviderName(StrEnum):
    GITHUB = "github"
    GITLAB = "gitlab"
    BITBUCKET = "bitbucket"


class InstallationStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"


class RepoVisibility(StrEnum):
    PUBLIC = "public"
    PRIVATE = "private"
    INTERNAL = "internal"


class SizeTier(StrEnum):
    HOT = "hot"
    WARM = "warm"
    COLD = "cold"


class WebhookDeliveryStatus(StrEnum):
    RECEIVED = "received"
    PROCESSED = "processed"
    FAILED = "failed"


class SnapshotState(StrEnum):
    PENDING = "pending"
    INDEXING = "indexing"
    READY = "ready"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class SecretRef:
    """Points to secret manager path only — never holds raw secrets (LLD §2.4)."""

    path: str

    def __post_init__(self) -> None:
        if not self.path.strip():
            raise ValidationError("secret_ref path is required")


class Installation:
    """SCM app installation (LLD §4.4 scm_installations)."""

    def __init__(
        self,
        *,
        id: UUID,
        tenant_id: UUID,
        provider: ScmProviderName,
        external_installation_id: str,
        account_login: str,
        secret_ref: SecretRef,
        status: InstallationStatus,
        created_at: datetime,
        updated_at: datetime,
        version: int = 1,
        deleted_at: datetime | None = None,
    ) -> None:
        self.id = id
        self.tenant_id = tenant_id
        self.provider = provider
        self.external_installation_id = external_installation_id
        self.account_login = account_login
        self.secret_ref = secret_ref
        self.status = status
        self.created_at = created_at
        self.updated_at = updated_at
        self.version = version
        self.deleted_at = deleted_at

    @classmethod
    def create(
        cls,
        *,
        tenant_id: UUID,
        provider: ScmProviderName,
        external_installation_id: str,
        account_login: str,
        secret_ref: SecretRef,
    ) -> Installation:
        now = datetime.now(UTC)
        return cls(
            id=new_uuid7(),
            tenant_id=tenant_id,
            provider=provider,
            external_installation_id=external_installation_id,
            account_login=account_login,
            secret_ref=secret_ref,
            status=InstallationStatus.ACTIVE,
            created_at=now,
            updated_at=now,
            version=1,
        )


class RepositoryConnection:
    """Connected repository under an installation (LLD §4.4 repositories)."""

    def __init__(
        self,
        *,
        id: UUID,
        tenant_id: UUID,
        installation_id: UUID,
        provider: ScmProviderName,
        external_repo_id: str,
        full_name: str,
        default_branch: str,
        visibility: RepoVisibility,
        size_tier: SizeTier,
        last_synced_at: datetime | None,
        created_at: datetime,
        updated_at: datetime,
        version: int = 1,
        deleted_at: datetime | None = None,
    ) -> None:
        self.id = id
        self.tenant_id = tenant_id
        self.installation_id = installation_id
        self.provider = provider
        self.external_repo_id = external_repo_id
        self.full_name = full_name
        self.default_branch = default_branch
        self.visibility = visibility
        self.size_tier = size_tier
        self.last_synced_at = last_synced_at
        self.created_at = created_at
        self.updated_at = updated_at
        self.version = version
        self.deleted_at = deleted_at

    @classmethod
    def connect(
        cls,
        *,
        tenant_id: UUID,
        installation_id: UUID,
        provider: ScmProviderName,
        external_repo_id: str,
        full_name: str,
        default_branch: str,
        visibility: RepoVisibility,
        size_tier: SizeTier = SizeTier.HOT,
    ) -> RepositoryConnection:
        if "/" not in full_name:
            raise ValidationError("full_name must be org/name")
        now = datetime.now(UTC)
        return cls(
            id=new_uuid7(),
            tenant_id=tenant_id,
            installation_id=installation_id,
            provider=provider,
            external_repo_id=external_repo_id,
            full_name=full_name,
            default_branch=default_branch,
            visibility=visibility,
            size_tier=size_tier,
            last_synced_at=now,
            created_at=now,
            updated_at=now,
            version=1,
        )

    def soft_delete(self) -> None:
        if self.deleted_at is not None:
            raise ConflictError("Repository already disconnected")
        now = datetime.now(UTC)
        self.deleted_at = now
        self.updated_at = now
        self.version += 1

    def mark_synced(self) -> None:
        now = datetime.now(UTC)
        self.last_synced_at = now
        self.updated_at = now
        self.version += 1


class WebhookDelivery:
    """Deduplicated inbound SCM webhook delivery (LLD §4.4 webhook_deliveries)."""

    def __init__(
        self,
        *,
        id: UUID,
        tenant_id: UUID,
        provider: ScmProviderName,
        delivery_id: str,
        event_type: str,
        payload_ref: str,
        status: WebhookDeliveryStatus,
        created_at: datetime,
        processed_at: datetime | None = None,
    ) -> None:
        self.id = id
        self.tenant_id = tenant_id
        self.provider = provider
        self.delivery_id = delivery_id
        self.event_type = event_type
        self.payload_ref = payload_ref
        self.status = status
        self.created_at = created_at
        self.processed_at = processed_at

    @classmethod
    def receive(
        cls,
        *,
        tenant_id: UUID,
        provider: ScmProviderName,
        delivery_id: str,
        event_type: str,
        payload_ref: str,
    ) -> WebhookDelivery:
        if not delivery_id.strip():
            raise ValidationError("delivery_id is required")
        return cls(
            id=new_uuid7(),
            tenant_id=tenant_id,
            provider=provider,
            delivery_id=delivery_id,
            event_type=event_type,
            payload_ref=payload_ref,
            status=WebhookDeliveryStatus.RECEIVED,
            created_at=datetime.now(UTC),
        )

    def mark_processed(self) -> None:
        self.status = WebhookDeliveryStatus.PROCESSED
        self.processed_at = datetime.now(UTC)

    def mark_failed(self) -> None:
        self.status = WebhookDeliveryStatus.FAILED
        self.processed_at = datetime.now(UTC)


class RepoSnapshot:
    """Immutable indexing unit for a commit (LLD §4.4 repo_snapshots)."""

    def __init__(
        self,
        *,
        id: UUID,
        tenant_id: UUID,
        repository_id: UUID,
        commit_sha: str,
        parent_commit_sha: str | None,
        manifest_ref: str,
        index_generation_id: UUID | None,
        state: SnapshotState,
        error_code: str | None,
        created_at: datetime,
        updated_at: datetime,
        version: int = 1,
    ) -> None:
        if len(commit_sha) != 40:
            raise DomainInvariantError("commit_sha must be 40 hex characters")
        self.id = id
        self.tenant_id = tenant_id
        self.repository_id = repository_id
        self.commit_sha = commit_sha.lower()
        self.parent_commit_sha = parent_commit_sha.lower() if parent_commit_sha else None
        self.manifest_ref = manifest_ref
        self.index_generation_id = index_generation_id
        self.state = state
        self.error_code = error_code
        self.created_at = created_at
        self.updated_at = updated_at
        self.version = version

    @classmethod
    def request(
        cls,
        *,
        tenant_id: UUID,
        repository_id: UUID,
        commit_sha: str,
        parent_commit_sha: str | None = None,
        manifest_ref: str = "",
    ) -> RepoSnapshot:
        now = datetime.now(UTC)
        return cls(
            id=new_uuid7(),
            tenant_id=tenant_id,
            repository_id=repository_id,
            commit_sha=commit_sha,
            parent_commit_sha=parent_commit_sha,
            manifest_ref=manifest_ref or f"snapshots/{repository_id}/{commit_sha}.json",
            index_generation_id=None,
            state=SnapshotState.PENDING,
            error_code=None,
            created_at=now,
            updated_at=now,
            version=1,
        )

    def mark_indexing(self) -> None:
        if self.state != SnapshotState.PENDING:
            raise ConflictError("Snapshot is not pending")
        self.state = SnapshotState.INDEXING
        self.updated_at = datetime.now(UTC)
        self.version += 1
