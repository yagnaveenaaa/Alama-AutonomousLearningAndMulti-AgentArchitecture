from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from knowledge_service.domain.models import MemoryItem, MemoryStatus
from knowledge_service.domain.repositories import MemoryContentStore, MemoryRepository


class RetentionJob:
    """Expiry + legal hold respect (LLD §2.8 / §8.4)."""

    def __init__(
        self,
        memories: MemoryRepository,
        content_store: MemoryContentStore,
    ) -> None:
        self._memories = memories
        self._content = content_store

    async def run_once(self, tenant_id: UUID, *, limit: int = 100) -> int:
        now = datetime.now(UTC)
        items, _ = await self._memories.list_for_tenant(
            tenant_id,
            status=MemoryStatus.ACTIVE.value,
            limit=limit,
            cursor=None,
        )
        expired = 0
        for item in items:
            if item.legal_hold:
                continue
            if item.expires_at is not None and item.expires_at <= now:
                await self._expire(item)
                expired += 1
        return expired

    async def expire_candidates_older_than(
        self, tenant_id: UUID, *, days: int = 180, limit: int = 100
    ) -> int:
        cutoff = datetime.now(UTC) - timedelta(days=days)
        items, _ = await self._memories.list_for_tenant(
            tenant_id,
            status=MemoryStatus.CANDIDATE.value,
            limit=limit,
            cursor=None,
        )
        expired = 0
        for item in items:
            if item.legal_hold:
                continue
            if item.created_at <= cutoff:
                await self._expire(item)
                expired += 1
        return expired

    async def _expire(self, item: MemoryItem) -> None:
        item.archive()
        await self._memories.save(item)
        await self._content.delete(item.content_ref)
