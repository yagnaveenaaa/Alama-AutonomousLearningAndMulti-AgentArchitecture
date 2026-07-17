from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from identity_service.domain.models import IsolationTier


@dataclass(frozen=True, slots=True)
class CreateTenantCommand:
    slug: str
    name: str
    home_region: str
    home_cell: str
    isolation_tier: IsolationTier
    plan: str
    data_residency: str
    owner_external_idp_sub: str
    owner_email: str | None = None
    owner_display_name: str | None = None


@dataclass(frozen=True, slots=True)
class CreateApiKeyCommand:
    tenant_id: UUID
    subject_id: UUID
    name: str
    scopes: tuple[str, ...]
    expires_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class IssuedApiKeyResult:
    id: UUID
    key_prefix: str
    plaintext_key: str
    name: str
    scopes: tuple[str, ...]
    expires_at: datetime | None


@dataclass(frozen=True, slots=True)
class ScimUserUpsertCommand:
    tenant_id: UUID
    external_idp_sub: str
    email: str | None
    display_name: str | None
    active: bool = True
