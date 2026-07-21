from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from knowledge_service.domain.models import MemoryScope, MemoryStatus, MemoryType, MessageRole


@dataclass(frozen=True, slots=True)
class CreateMemoryCommand:
    tenant_id: UUID
    subject_id: UUID
    scope: MemoryScope
    memory_type: MemoryType
    title: str
    content: str
    confidence: float = 0.8
    provenance: dict[str, Any] = field(default_factory=dict)
    acl: dict[str, Any] = field(default_factory=dict)
    repository_id: UUID | None = None
    task_id: UUID | None = None
    promote: bool = False
    policy_constraints: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PatchMemoryCommand:
    tenant_id: UUID
    subject_id: UUID
    memory_id: UUID
    title: str | None = None
    confidence: float | None = None
    acl: dict[str, Any] | None = None
    status: MemoryStatus | None = None


@dataclass(frozen=True, slots=True)
class DeleteMemoryCommand:
    tenant_id: UUID
    subject_id: UUID
    memory_id: UUID


@dataclass(frozen=True, slots=True)
class CreateConversationCommand:
    tenant_id: UUID
    subject_id: UUID
    title: str
    task_id: UUID | None = None
    repository_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class PostMessageCommand:
    tenant_id: UUID
    subject_id: UUID
    conversation_id: UUID
    content: str
    role: MessageRole = MessageRole.USER
    start_task: bool = False
