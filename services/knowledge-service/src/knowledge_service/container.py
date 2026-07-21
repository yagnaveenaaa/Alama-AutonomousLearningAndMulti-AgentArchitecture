from __future__ import annotations

from dataclasses import dataclass

from knowledge_service.adapters.memory import (
    InMemoryConversationRepository,
    InMemoryKnowledgeStore,
    InMemoryMemoryRepository,
    InMemoryMessageRepository,
)
from knowledge_service.application.conversations import ConversationService
from knowledge_service.application.memory import MemoryService
from knowledge_service.application.retention import RetentionJob
from knowledge_service.config import KnowledgeSettings
from knowledge_service.writegate.gate import MemoryWriteGate


@dataclass
class KnowledgeContainer:
    store: InMemoryKnowledgeStore
    memories: MemoryService
    conversations: ConversationService
    retention: RetentionJob
    write_gate: MemoryWriteGate


def build_container(settings: KnowledgeSettings | None = None) -> KnowledgeContainer:
    settings = settings or KnowledgeSettings()
    store = InMemoryKnowledgeStore()
    memory_repo = InMemoryMemoryRepository(store)
    conversation_repo = InMemoryConversationRepository(store)
    message_repo = InMemoryMessageRepository(store)
    write_gate = MemoryWriteGate(memory_repo, min_confidence=settings.min_confidence)
    return KnowledgeContainer(
        store=store,
        memories=MemoryService(memory_repo, store.content, write_gate),
        conversations=ConversationService(conversation_repo, message_repo, store.content),
        retention=RetentionJob(memory_repo, store.content),
        write_gate=write_gate,
    )
