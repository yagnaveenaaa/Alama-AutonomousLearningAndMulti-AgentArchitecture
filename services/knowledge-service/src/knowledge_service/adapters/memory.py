from __future__ import annotations

from uuid import UUID

from alama_common.pagination import decode_cursor, encode_cursor

from knowledge_service.domain.models import Conversation, MemoryItem, Message


class InMemoryContentStore:
    """Encrypted object payload stand-in (LLD §2.8 MemoryContentStore)."""

    def __init__(self) -> None:
        self._objects: dict[str, dict[str, object]] = {}
        self.deleted: list[str] = []

    async def put(self, content_ref: str, payload: dict[str, object]) -> str:
        self._objects[content_ref] = dict(payload)
        return content_ref

    async def get(self, content_ref: str) -> dict[str, object] | None:
        payload = self._objects.get(content_ref)
        return dict(payload) if payload is not None else None

    async def delete(self, content_ref: str) -> None:
        self._objects.pop(content_ref, None)
        self.deleted.append(content_ref)


class InMemoryKnowledgeStore:
    def __init__(self) -> None:
        self.memories: dict[UUID, MemoryItem] = {}
        self.conversations: dict[UUID, Conversation] = {}
        self.messages: dict[UUID, list[Message]] = {}
        self.content = InMemoryContentStore()


class InMemoryMemoryRepository:
    def __init__(self, store: InMemoryKnowledgeStore) -> None:
        self._store = store

    async def get_by_id(self, tenant_id: UUID, memory_id: UUID) -> MemoryItem | None:
        item = self._store.memories.get(memory_id)
        if item is None or item.tenant_id != tenant_id:
            return None
        return item

    async def get_active_by_hash(self, tenant_id: UUID, content_hash: str) -> MemoryItem | None:
        for item in self._store.memories.values():
            if (
                item.tenant_id == tenant_id
                and item.content_hash == content_hash
                and item.status.value == "active"
                and item.deleted_at is None
            ):
                return item
        return None

    async def save(self, item: MemoryItem) -> None:
        self._store.memories[item.id] = item

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
    ) -> tuple[list[MemoryItem], str | None]:
        items = [
            m
            for m in self._store.memories.values()
            if m.tenant_id == tenant_id and m.deleted_at is None
        ]
        if scope:
            items = [m for m in items if m.scope.value == scope]
        if status:
            items = [m for m in items if m.status.value == status]
        if memory_type:
            items = [m for m in items if m.memory_type.value == memory_type]
        if repository_id:
            items = [m for m in items if m.repository_id == repository_id]
        if subject_id:
            items = [m for m in items if m.subject_id == subject_id]
        if task_id:
            items = [m for m in items if m.task_id == task_id]
        if query:
            q = query.lower()
            items = [m for m in items if q in m.title.lower()]
        items.sort(key=lambda m: m.created_at, reverse=True)
        offset = 0
        if cursor:
            offset = int(decode_cursor(cursor).get("offset", 0))
        page = items[offset : offset + limit]
        next_cursor = (
            encode_cursor({"offset": offset + limit}) if offset + limit < len(items) else None
        )
        return page, next_cursor


class InMemoryConversationRepository:
    def __init__(self, store: InMemoryKnowledgeStore) -> None:
        self._store = store

    async def get_by_id(self, tenant_id: UUID, conversation_id: UUID) -> Conversation | None:
        item = self._store.conversations.get(conversation_id)
        if item is None or item.tenant_id != tenant_id:
            return None
        return item

    async def save(self, conversation: Conversation) -> None:
        self._store.conversations[conversation.id] = conversation

    async def list_for_tenant(
        self,
        tenant_id: UUID,
        *,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[Conversation], str | None]:
        items = [
            c
            for c in self._store.conversations.values()
            if c.tenant_id == tenant_id and c.deleted_at is None
        ]
        items.sort(key=lambda c: c.updated_at, reverse=True)
        offset = 0
        if cursor:
            offset = int(decode_cursor(cursor).get("offset", 0))
        page = items[offset : offset + limit]
        next_cursor = (
            encode_cursor({"offset": offset + limit}) if offset + limit < len(items) else None
        )
        return page, next_cursor


class InMemoryMessageRepository:
    def __init__(self, store: InMemoryKnowledgeStore) -> None:
        self._store = store

    async def next_sequence(self, conversation_id: UUID) -> int:
        return len(self._store.messages.get(conversation_id, [])) + 1

    async def save(self, message: Message) -> None:
        self._store.messages.setdefault(message.conversation_id, []).append(message)

    async def list_for_conversation(
        self, conversation_id: UUID, *, limit: int
    ) -> list[Message]:
        items = list(self._store.messages.get(conversation_id, []))
        items.sort(key=lambda m: m.sequence)
        return items[:limit]
