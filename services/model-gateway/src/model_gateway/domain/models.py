from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import UUID

from alama_common.errors import ValidationError
from alama_common.ids import new_uuid7


class ModelCapability(StrEnum):
    COMPLETE = "complete"
    EMBED = "embed"
    RERANK = "rerank"
    JSON = "json"


class ModelTier(StrEnum):
    STRONG = "strong"
    MID = "mid"
    EMBEDDING = "embedding"
    RERANK = "rerank"


@dataclass(frozen=True, slots=True)
class ModelProfile:
    name: str
    provider: str
    tier: ModelTier
    capabilities: frozenset[ModelCapability]
    residency: str
    cost_per_1k_micros: int
    max_context_tokens: int


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: str
    content: str

    def __post_init__(self) -> None:
        if self.role not in {"system", "user", "assistant"}:
            raise ValidationError("role must be system|user|assistant")
        if not self.content.strip():
            raise ValidationError("message content is required")


@dataclass(frozen=True, slots=True)
class ModelRequest:
    tenant_id: UUID
    task_id: UUID | None
    purpose: str
    capability: ModelCapability
    preferred_tier: ModelTier
    residency: str
    messages: tuple[ChatMessage, ...] = ()
    texts: tuple[str, ...] = ()
    query: str | None = None
    documents: tuple[str, ...] = ()
    template_name: str | None = None
    template_version: str | None = None
    template_inputs: dict[str, Any] = field(default_factory=dict)
    json_schema_name: str | None = None
    max_tokens: int = 2048

    def __post_init__(self) -> None:
        if self.capability == ModelCapability.COMPLETE and not (
            self.messages or self.template_name
        ):
            raise ValidationError("complete requires messages or template_name")
        if self.capability == ModelCapability.EMBED and not self.texts:
            raise ValidationError("embed requires texts")
        if self.capability == ModelCapability.RERANK and (
            not self.query or not self.documents
        ):
            raise ValidationError("rerank requires query and documents")


@dataclass(frozen=True, slots=True)
class CompletionResult:
    request_id: UUID
    model: str
    provider: str
    content: str
    parsed_json: dict[str, Any] | None
    input_tokens: int
    output_tokens: int
    fallback_used: bool


@dataclass(frozen=True, slots=True)
class EmbeddingResult:
    request_id: UUID
    model: str
    provider: str
    vectors: tuple[tuple[float, ...], ...]
    input_tokens: int
    dimension: int


@dataclass(frozen=True, slots=True)
class RerankResult:
    request_id: UUID
    model: str
    provider: str
    ranked_indices: tuple[int, ...]
    scores: tuple[float, ...]
    input_tokens: int


@dataclass(frozen=True, slots=True)
class UsageRecord:
    id: UUID
    tenant_id: UUID
    task_id: UUID | None
    category: str
    model: str
    provider: str
    quantity: int
    unit: str
    purpose: str

    @classmethod
    def tokens(
        cls,
        *,
        tenant_id: UUID,
        task_id: UUID | None,
        model: str,
        provider: str,
        quantity: int,
        purpose: str,
        category: str = "model_tokens",
    ) -> UsageRecord:
        return cls(
            id=new_uuid7(),
            tenant_id=tenant_id,
            task_id=task_id,
            category=category,
            model=model,
            provider=provider,
            quantity=quantity,
            unit="tokens",
            purpose=purpose,
        )


@dataclass(frozen=True, slots=True)
class PromptTemplate:
    name: str
    version: str
    body: str
    output_schema: str

    @property
    def key(self) -> str:
        return f"{self.name}.{self.version}"
