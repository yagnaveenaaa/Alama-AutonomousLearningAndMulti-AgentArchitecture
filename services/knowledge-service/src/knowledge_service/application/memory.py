from __future__ import annotations

from uuid import UUID

from alama_common.errors import DomainInvariantError, NotFoundError
from alama_common.ids import new_uuid7

from knowledge_service.application.dto import (
    CreateMemoryCommand,
    DeleteMemoryCommand,
    PatchMemoryCommand,
)
from knowledge_service.domain.models import MemoryItem, MemoryStatus
from knowledge_service.domain.repositories import MemoryContentStore, MemoryRepository
from knowledge_service.writegate.gate import MemoryWriteGate


class MemoryService:
    """CRUD + promote candidates through write gate (LLD §2.8)."""

    def __init__(
        self,
        memories: MemoryRepository,
        content_store: MemoryContentStore,
        write_gate: MemoryWriteGate,
    ) -> None:
        self._memories = memories
        self._content = content_store
        self._gate = write_gate

    async def create(self, command: CreateMemoryCommand) -> MemoryItem:
        target_status = (
            MemoryStatus.ACTIVE if command.promote else MemoryStatus.CANDIDATE
        )
        gate = await self._gate.evaluate_create(
            tenant_id=command.tenant_id,
            content=command.content,
            confidence=command.confidence,
            status=target_status,
            policy_constraints=command.policy_constraints,
        )
        if not gate.allowed:
            raise DomainInvariantError(
                "Memory write gate rejected content",
                details={"reasons": list(gate.reasons)},
            )
        content_ref = f"memories/{command.tenant_id}/{new_uuid7()}.json"
        await self._content.put(
            content_ref,
            {"content": gate.normalized_content, "title": command.title},
        )
        subject_id = command.subject_id if command.scope.value == "user" else None
        item = MemoryItem.create(
            tenant_id=command.tenant_id,
            scope=command.scope,
            memory_type=command.memory_type,
            title=command.title.strip(),
            content_ref=content_ref,
            content_hash=gate.content_hash,
            provenance=dict(command.provenance),
            confidence=command.confidence,
            acl=dict(command.acl) or {"subject_ids": [str(command.subject_id)]},
            status=MemoryStatus.CANDIDATE,
            repository_id=command.repository_id,
            subject_id=subject_id,
            task_id=command.task_id,
        )
        if command.promote:
            promote_gate = await self._gate.evaluate_promote(
                tenant_id=command.tenant_id,
                content_hash=gate.content_hash,
                confidence=command.confidence,
            )
            if not promote_gate.allowed:
                raise DomainInvariantError(
                    "Memory promotion rejected",
                    details={"reasons": list(promote_gate.reasons)},
                )
            item.promote()
        await self._memories.save(item)
        return item

    async def get(self, tenant_id: UUID, memory_id: UUID) -> MemoryItem:
        item = await self._memories.get_by_id(tenant_id, memory_id)
        if item is None or item.deleted_at is not None:
            raise NotFoundError("Memory not found")
        return item

    async def list(
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
        return await self._memories.list_for_tenant(
            tenant_id,
            scope=scope,
            status=status,
            memory_type=memory_type,
            repository_id=repository_id,
            subject_id=subject_id,
            task_id=task_id,
            query=query,
            limit=limit,
            cursor=cursor,
        )

    async def patch(self, command: PatchMemoryCommand) -> MemoryItem:
        item = await self.get(command.tenant_id, command.memory_id)
        if command.status == MemoryStatus.ACTIVE:
            gate = await self._gate.evaluate_promote(
                tenant_id=command.tenant_id,
                content_hash=item.content_hash,
                confidence=(
                    command.confidence if command.confidence is not None else item.confidence
                ),
            )
            if not gate.allowed:
                raise DomainInvariantError(
                    "Memory promotion rejected",
                    details={"reasons": list(gate.reasons)},
                )
        item.patch(
            title=command.title,
            confidence=command.confidence,
            acl=command.acl,
            status=command.status,
        )
        await self._memories.save(item)
        return item

    async def delete(self, command: DeleteMemoryCommand) -> None:
        item = await self.get(command.tenant_id, command.memory_id)
        item.soft_delete()
        await self._memories.save(item)
        await self._content.delete(item.content_ref)
