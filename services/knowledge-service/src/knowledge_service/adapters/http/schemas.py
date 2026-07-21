from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from knowledge_service.domain.models import MemoryScope, MemoryStatus, MemoryType, MessageRole


class HealthResponse(BaseModel):
    status: str
    service: str


class CreateMemoryRequest(BaseModel):
    scope: MemoryScope
    memory_type: MemoryType
    title: str = Field(min_length=1, max_length=500)
    content: str = Field(min_length=1, max_length=100_000)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    provenance: dict[str, Any] = Field(default_factory=dict)
    acl: dict[str, Any] = Field(default_factory=dict)
    repository_id: UUID | None = None
    task_id: UUID | None = None
    promote: bool = False
    policy_constraints: dict[str, Any] = Field(default_factory=dict)


class PatchMemoryRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    acl: dict[str, Any] | None = None
    status: MemoryStatus | None = None


class MemoryResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    scope: str
    memory_type: str
    repository_id: UUID | None
    subject_id: UUID | None
    task_id: UUID | None
    title: str
    content_ref: str
    content_hash: str
    provenance: dict[str, Any]
    confidence: float
    acl: dict[str, Any]
    embedding_model: str | None
    vector_ref: str | None
    expires_at: datetime | None
    legal_hold: bool
    status: str
    created_at: datetime
    updated_at: datetime
    version: int


class MemoryListResponse(BaseModel):
    items: list[MemoryResponse]
    next_cursor: str | None = None


class CreateConversationRequest(BaseModel):
    title: str | None = Field(default=None, max_length=500)
    task_id: UUID | None = None
    repository_id: UUID | None = None


class ConversationResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    task_id: UUID | None
    repository_id: UUID | None
    title: str
    created_at: datetime
    updated_at: datetime
    version: int


class ConversationListResponse(BaseModel):
    items: list[ConversationResponse]
    next_cursor: str | None = None


class PostMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=100_000)
    role: MessageRole = MessageRole.USER
    start_task: bool = False


class MessageResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    conversation_id: UUID
    role: str
    content_ref: str
    token_estimate: int
    sequence: int
    created_at: datetime
    task_accepted: bool = False
