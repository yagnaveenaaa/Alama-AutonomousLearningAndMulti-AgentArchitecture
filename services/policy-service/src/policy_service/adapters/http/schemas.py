from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from policy_service.domain.models import PolicyAction


class HealthResponse(BaseModel):
    status: str
    service: str


class EvaluatePolicyRequest(BaseModel):
    action: PolicyAction
    attributes: dict[str, Any] = Field(default_factory=dict)
    policy_version: str | None = None
    dry_run: bool = False


class PolicyDecisionResponse(BaseModel):
    effect: str
    required_approvals: list[str]
    constraints: dict[str, Any]
    policy_version: str
    reasons: list[str]


class PolicyBundleResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    version: str
    bundle_ref: str
    status: str
    checksum: str
    activated_at: str | None
    created_at: str


class PolicyBundleListResponse(BaseModel):
    items: list[PolicyBundleResponse]


class UpsertDraftBundleRequest(BaseModel):
    version: str = Field(min_length=1, max_length=128)
    rules: list[dict[str, Any]] = Field(min_length=1)
