from __future__ import annotations

import hashlib
import re
from typing import Any
from uuid import UUID

from alama_common.errors import ValidationError

from knowledge_service.domain.models import MemoryStatus, WriteGateResult
from knowledge_service.domain.repositories import MemoryRepository

_EMAIL = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
_SECRET = re.compile(
    r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*['\"]?\S{8,}|sk-[A-Za-z0-9]{20,}"
)


class MemoryWriteGate:
    """PII/secret/dedupe/confidence/policy promotion rules (LLD §2.8 / §8)."""

    def __init__(
        self,
        memories: MemoryRepository,
        *,
        min_confidence: float,
    ) -> None:
        self._memories = memories
        self._min_confidence = min_confidence

    async def evaluate_create(
        self,
        *,
        tenant_id: UUID,
        content: str,
        confidence: float,
        status: MemoryStatus,
        policy_constraints: dict[str, Any] | None = None,
    ) -> WriteGateResult:
        normalized = content.strip()
        if not normalized:
            raise ValidationError("Memory content is required")
        reasons: list[str] = []
        if _EMAIL.search(normalized):
            reasons.append("pii_email_detected")
        if _SECRET.search(normalized):
            reasons.append("secret_detected")
        if confidence < self._min_confidence:
            reasons.append("confidence_below_threshold")
        constraints = policy_constraints or {}
        if constraints.get("data_class") in {"secret", "restricted"}:
            reasons.append("policy_data_class_denied")
        content_hash = self._hash(normalized)
        if status == MemoryStatus.ACTIVE:
            existing = await self._memories.get_active_by_hash(tenant_id, content_hash)
            if existing is not None:
                reasons.append("duplicate_active_content")
        return WriteGateResult(
            allowed=not reasons,
            reasons=tuple(reasons),
            normalized_content=normalized,
            content_hash=content_hash,
        )

    async def evaluate_promote(
        self,
        *,
        tenant_id: UUID,
        content_hash: str,
        confidence: float,
    ) -> WriteGateResult:
        reasons: list[str] = []
        if confidence < self._min_confidence:
            reasons.append("confidence_below_threshold")
        existing = await self._memories.get_active_by_hash(tenant_id, content_hash)
        if existing is not None:
            reasons.append("duplicate_active_content")
        return WriteGateResult(
            allowed=not reasons,
            reasons=tuple(reasons),
            content_hash=content_hash,
        )

    @staticmethod
    def _hash(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()
