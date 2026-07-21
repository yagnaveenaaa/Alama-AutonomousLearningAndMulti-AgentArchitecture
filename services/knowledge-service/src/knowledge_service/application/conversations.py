from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from alama_common.errors import NotFoundError, ValidationError
from alama_common.ids import new_uuid7

from knowledge_service.application.dto import CreateConversationCommand, PostMessageCommand
from knowledge_service.domain.models import Conversation, Message, MessageRole
from knowledge_service.domain.repositories import (
    ConversationRepository,
    MemoryContentStore,
    MessageRepository,
)


@dataclass(frozen=True, slots=True)
class PostMessageResult:
    message: Message
    conversation: Conversation
    task_accepted: bool


class ConversationService:
    """Thread + message lifecycle (LLD §2.8 / §5.5)."""

    def __init__(
        self,
        conversations: ConversationRepository,
        messages: MessageRepository,
        content_store: MemoryContentStore,
    ) -> None:
        self._conversations = conversations
        self._messages = messages
        self._content = content_store

    async def create(self, command: CreateConversationCommand) -> Conversation:
        title = command.title.strip() or "Untitled conversation"
        conversation = Conversation.create(
            tenant_id=command.tenant_id,
            title=title,
            task_id=command.task_id,
            repository_id=command.repository_id,
        )
        await self._conversations.save(conversation)
        return conversation

    async def list(
        self,
        tenant_id: UUID,
        *,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[Conversation], str | None]:
        return await self._conversations.list_for_tenant(
            tenant_id, limit=limit, cursor=cursor
        )

    async def get(self, tenant_id: UUID, conversation_id: UUID) -> Conversation:
        conversation = await self._conversations.get_by_id(tenant_id, conversation_id)
        if conversation is None or conversation.deleted_at is not None:
            raise NotFoundError("Conversation not found")
        return conversation

    async def post_message(self, command: PostMessageCommand) -> PostMessageResult:
        content = command.content.strip()
        if not content:
            raise ValidationError("Message content is required")
        conversation = await self.get(command.tenant_id, command.conversation_id)
        sequence = await self._messages.next_sequence(conversation.id)
        content_ref = f"messages/{command.tenant_id}/{conversation.id}/{sequence}.json"
        await self._content.put(
            content_ref,
            {
                "content": content,
                "role": command.role.value,
                "subject_id": str(command.subject_id),
            },
        )
        message = Message.create(
            tenant_id=command.tenant_id,
            conversation_id=conversation.id,
            role=command.role,
            content_ref=content_ref,
            token_estimate=max(1, len(content) // 4),
            sequence=sequence,
        )
        await self._messages.save(message)
        conversation.updated_at = message.created_at
        conversation.version += 1
        await self._conversations.save(conversation)

        task_accepted = False
        if command.start_task and command.role == MessageRole.USER:
            # Task start is signaled to task-service by BFF; we acknowledge 202 intent.
            task_accepted = True
            _ = new_uuid7()
        return PostMessageResult(
            message=message,
            conversation=conversation,
            task_accepted=task_accepted,
        )
