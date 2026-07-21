from __future__ import annotations

from typing import Protocol
from uuid import UUID

from model_gateway.domain.models import (
    CompletionResult,
    EmbeddingResult,
    ModelProfile,
    ModelRequest,
    PromptTemplate,
    RerankResult,
    UsageRecord,
)


class ProviderAdapter(Protocol):
    """Vendor SDK isolation (LLD §2.9)."""

    name: str

    async def complete(
        self, request: ModelRequest, profile: ModelProfile
    ) -> CompletionResult: ...

    async def embed(
        self, request: ModelRequest, profile: ModelProfile
    ) -> EmbeddingResult: ...

    async def rerank(
        self, request: ModelRequest, profile: ModelProfile
    ) -> RerankResult: ...


class PromptTemplateRegistry(Protocol):
    async def get(self, name: str, version: str | None = None) -> PromptTemplate: ...


class UsageEmitter(Protocol):
    async def emit(self, record: UsageRecord) -> None: ...


class QuotaPort(Protocol):
    async def consume(self, tenant_id: UUID, tokens: int) -> None: ...


class ModelGateway(Protocol):
    async def complete(self, request: ModelRequest) -> CompletionResult: ...

    async def embed(self, request: ModelRequest) -> EmbeddingResult: ...

    async def rerank(self, request: ModelRequest) -> RerankResult: ...
