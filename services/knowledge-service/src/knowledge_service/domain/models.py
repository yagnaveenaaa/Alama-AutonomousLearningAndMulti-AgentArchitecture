from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from alama_common.errors import ConflictError, DomainInvariantError
from alama_common.ids import new_uuid7


class MemoryScope(StrEnum):
    USER = "user"
    REPO = "repo"
    ORG = "org"
    TASK = "task"
    REFLECTION = "reflection"


class MemoryType(StrEnum):
    """Memory kinds aligned to LLD §8.1."""

    WORKING = "working"
    ORG_SEMANTIC = "org_semantic"
    USER_FACT = "user_fact"
    REPO_CONVENTION = "repo_convention"
    CONVERSATION = "conversation"
    REFLECTION = "reflection"


class MemoryStatus(StrEnum):
    CANDIDATE = "candidate"
    ACTIVE = "active"
    ARCHIVED = "archived"
    REJECTED = "rejected"


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class MemoryItem:
    """Governed long-term memory aggregate (LLD §4.6 / §8)."""

    id: UUID
    tenant_id: UUID
    scope: MemoryScope
    memory_type: MemoryType
    title: str
    content_ref: str
    content_hash: str
    provenance: dict[str, Any]
    confidence: float
    acl: dict[str, Any]
    status: MemoryStatus
    created_at: datetime
    updated_at: datetime
    version: int
    repository_id: UUID | None = None
    subject_id: UUID | None = None
    task_id: UUID | None = None
    embedding_model: str | None = None
    vector_ref: str | None = None
    expires_at: datetime | None = None
    legal_hold: bool = False
    deleted_at: datetime | None = None

    @classmethod
    def create(
        cls,
        *,
        tenant_id: UUID,
        scope: MemoryScope,
        memory_type: MemoryType,
        title: str,
        content_ref: str,
        content_hash: str,
        provenance: dict[str, Any],
        confidence: float,
        acl: dict[str, Any],
        status: MemoryStatus = MemoryStatus.CANDIDATE,
        repository_id: UUID | None = None,
        subject_id: UUID | None = None,
        task_id: UUID | None = None,
        expires_at: datetime | None = None,
    ) -> MemoryItem:
        now = datetime.now(UTC)
        return cls(
            id=new_uuid7(),
            tenant_id=tenant_id,
            scope=scope,
            memory_type=memory_type,
            repository_id=repository_id,
            subject_id=subject_id,
            task_id=task_id,
            title=title,
            content_ref=content_ref,
            content_hash=content_hash,
            provenance=provenance,
            confidence=confidence,
            acl=acl,
            embedding_model=None,
            vector_ref=None,
            expires_at=expires_at,
            legal_hold=False,
            status=status,
            created_at=now,
            updated_at=now,
            version=1,
            deleted_at=None,
        )

    def promote(self) -> None:
        if self.status != MemoryStatus.CANDIDATE:
            raise DomainInvariantError("Only candidate memories can be promoted")
        self.status = MemoryStatus.ACTIVE
        self.updated_at = datetime.now(UTC)
        self.version += 1

    def archive(self) -> None:
        if self.status not in {MemoryStatus.ACTIVE, MemoryStatus.CANDIDATE}:
            raise DomainInvariantError("Cannot archive memory in current status")
        self.status = MemoryStatus.ARCHIVED
        self.updated_at = datetime.now(UTC)
        self.version += 1

    def reject(self, reason: str) -> None:
        if self.status != MemoryStatus.CANDIDATE:
            raise DomainInvariantError("Only candidate memories can be rejected")
        self.status = MemoryStatus.REJECTED
        self.provenance = {**self.provenance, "rejection_reason": reason}
        self.updated_at = datetime.now(UTC)
        self.version += 1

    def soft_delete(self) -> None:
        if self.legal_hold:
            raise ConflictError("Memory is under legal hold")
        if self.deleted_at is not None:
            return
        self.deleted_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)
        self.version += 1

    def patch(
        self,
        *,
        title: str | None = None,
        confidence: float | None = None,
        acl: dict[str, Any] | None = None,
        status: MemoryStatus | None = None,
    ) -> None:
        if title is not None:
            self.title = title
        if confidence is not None:
            self.confidence = confidence
        if acl is not None:
            self.acl = acl
        if status is not None:
            if status == MemoryStatus.ACTIVE:
                self.promote()
                return
            if status == MemoryStatus.ARCHIVED:
                self.archive()
                return
            if status == MemoryStatus.REJECTED:
                self.reject("manual_reject")
                return
            self.status = status
        self.updated_at = datetime.now(UTC)
        self.version += 1


@dataclass
class Conversation:
    id: UUID
    tenant_id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
    version: int
    task_id: UUID | None = None
    repository_id: UUID | None = None
    deleted_at: datetime | None = None

    @classmethod
    def create(
        cls,
        *,
        tenant_id: UUID,
        title: str,
        task_id: UUID | None = None,
        repository_id: UUID | None = None,
    ) -> Conversation:
        now = datetime.now(UTC)
        return cls(
            id=new_uuid7(),
            tenant_id=tenant_id,
            task_id=task_id,
            repository_id=repository_id,
            title=title,
            created_at=now,
            updated_at=now,
            version=1,
            deleted_at=None,
        )

    def soft_delete(self) -> None:
        if self.deleted_at is not None:
            return
        self.deleted_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)
        self.version += 1


@dataclass
class Message:
    id: UUID
    tenant_id: UUID
    conversation_id: UUID
    role: MessageRole
    content_ref: str
    token_estimate: int
    sequence: int
    created_at: datetime

    @classmethod
    def create(
        cls,
        *,
        tenant_id: UUID,
        conversation_id: UUID,
        role: MessageRole,
        content_ref: str,
        token_estimate: int,
        sequence: int,
    ) -> Message:
        return cls(
            id=new_uuid7(),
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            role=role,
            content_ref=content_ref,
            token_estimate=token_estimate,
            sequence=sequence,
            created_at=datetime.now(UTC),
        )


@dataclass(frozen=True, slots=True)
class WriteGateResult:
    allowed: bool
    reasons: tuple[str, ...] = ()
    normalized_content: str = ""
    content_hash: str = ""
