from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from repository_service.domain.models import ScmProviderName, SnapshotState


class RegisterInstallationRequest(BaseModel):
    provider: ScmProviderName
    external_installation_id: str
    account_login: str
    secret_ref_path: str = Field(min_length=1)


class InstallationResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    provider: ScmProviderName
    external_installation_id: str
    account_login: str
    status: str


class ConnectRepositoryRequest(BaseModel):
    provider: ScmProviderName
    installation_id: UUID
    external_repo_id: str = Field(min_length=1)


class RepositoryResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    installation_id: UUID
    provider: ScmProviderName
    external_repo_id: str
    full_name: str
    default_branch: str
    visibility: str
    size_tier: str
    last_synced_at: datetime | None
    created_at: datetime
    updated_at: datetime


class RepositoryListResponse(BaseModel):
    items: list[RepositoryResponse]
    next_cursor: str | None = None


class ReindexRequest(BaseModel):
    ref: str | None = None


class ReindexResponse(BaseModel):
    snapshot_id: UUID


class SnapshotResponse(BaseModel):
    id: UUID
    repository_id: UUID
    commit_sha: str
    parent_commit_sha: str | None
    state: SnapshotState
    index_generation_id: UUID | None
    created_at: datetime


class SnapshotListResponse(BaseModel):
    items: list[SnapshotResponse]
    next_cursor: str | None = None


class IndexStatusResponse(BaseModel):
    repository_id: UUID
    latest_snapshot_id: UUID | None
    latest_commit_sha: str | None
    state: str | None
    index_generation_id: UUID | None


class HealthResponse(BaseModel):
    status: str
    service: str
