from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    service: str


class MintCapabilityRequest(BaseModel):
    task_id: UUID
    tool: str = Field(min_length=1, max_length=64)
    paths: list[str] = Field(default_factory=lambda: ["."])


class MintCapabilityResponse(BaseModel):
    token: str
    token_id: UUID
    tool: str
    paths: list[str]
    expires_at: str
    policy_version: str


class InvokeRequest(BaseModel):
    task_id: UUID
    tool: str = Field(min_length=1, max_length=64)
    args: dict[str, Any] = Field(default_factory=dict)
    capability: str = Field(min_length=1)


class ToolReceiptResponse(BaseModel):
    receipt_id: UUID
    tool: str
    inputs_hash: str
    output_ref: str | None
    output_inline: str | None
    duration_ms: int
    policy_version: str
    capability_id: UUID
    ok: bool


class InvokeResponse(BaseModel):
    ok: bool
    output: str
    receipt: ToolReceiptResponse
