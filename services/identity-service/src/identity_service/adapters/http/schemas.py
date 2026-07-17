from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from identity_service.domain.models import IsolationTier


class CreateTenantRequest(BaseModel):
    slug: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1)
    home_region: str
    home_cell: str
    isolation_tier: IsolationTier = IsolationTier.SHARED
    plan: str = "free"
    data_residency: str
    owner_external_idp_sub: str
    owner_email: str | None = None
    owner_display_name: str | None = None


class TenantResponse(BaseModel):
    id: UUID
    slug: str
    name: str
    home_region: str
    home_cell: str
    isolation_tier: IsolationTier
    plan: str
    status: str
    data_residency: str
    created_at: datetime
    updated_at: datetime
    version: int


class SubjectResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    external_idp_sub: str
    email: str | None
    display_name: str | None
    status: str
    roles: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class SubjectListResponse(BaseModel):
    items: list[SubjectResponse]
    next_cursor: str | None = None


class CreateApiKeyRequest(BaseModel):
    name: str = Field(min_length=1)
    scopes: list[str] = Field(min_length=1)
    expires_at: datetime | None = None
    subject_id: UUID | None = None


class CreateApiKeyResponse(BaseModel):
    id: UUID
    key_prefix: str
    key_once: str
    name: str
    scopes: list[str]
    expires_at: datetime | None


class HealthResponse(BaseModel):
    status: str
    service: str
