from __future__ import annotations

from typing import Protocol
from uuid import UUID

from knowledge_service.domain.models import Conversation, MemoryItem, Message


class MemoryRepository(Protocol):
    async def get_by_id(self, tenant_id: UUID, memory_id: UUID) -> MemoryItem | None: ...

    async def get_active_by_hash(self, tenant_id: UUID, content_hash: str) -> MemoryItem | None: ...

    async def save(self, item: MemoryItem) -> None: ...

    async def list_for_tenant(
        self,
        tenant_id: UUID,
        *,
        scope: str | None = None,
        status: str | None = None,
        memory_type: str | None = None,
        repository_id: UUID | None = None,
        subject_id: UUID | None = None,
        task_id: UUID | None = None,
        query: str | None = None,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[MemoryItem], str | None]: ...


class ConversationRepository(Protocol):
    async def get_by_id(self, tenant_id: UUID, conversation_id: UUID) -> Conversation | None: ...

    async def save(self, conversation: Conversation) -> None: ...

    async def list_for_tenant(
        self,
        tenant_id: UUID,
        *,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[Conversation], str | None]: ...


class MessageRepository(Protocol):
    async def next_sequence(self, conversation_id: UUID) -> int: ...

    async def save(self, message: Message) -> None: ...

    async def list_for_conversation(
        self, conversation_id: UUID, *, limit: int
    ) -> list[Message]: ...


class MemoryContentStore(Protocol):
    """Encrypted object payloads (LLD §2.8)."""

    async def put(self, content_ref: str, payload: dict[str, object]) -> str: ...

    async def get(self, content_ref: str) -> dict[str, object] | None: ...

    async def delete(self, content_ref: str) -> None: ...
