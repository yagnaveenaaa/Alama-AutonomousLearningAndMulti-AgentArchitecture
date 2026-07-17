from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from repository_service.domain.models import ScmProviderName


@dataclass(frozen=True, slots=True)
class ConnectRepositoryCommand:
    tenant_id: UUID
    provider: ScmProviderName
    installation_id: UUID
    external_repo_id: str


@dataclass(frozen=True, slots=True)
class RegisterInstallationCommand:
    tenant_id: UUID
    provider: ScmProviderName
    external_installation_id: str
    account_login: str
    secret_ref_path: str


@dataclass(frozen=True, slots=True)
class ReindexCommand:
    tenant_id: UUID
    repository_id: UUID
    ref: str | None = None


@dataclass(frozen=True, slots=True)
class IngestWebhookCommand:
    tenant_id: UUID
    provider: ScmProviderName
    delivery_id: str
    event_type: str
    body: bytes
    signature_header: str | None
    secret_ref_path: str
