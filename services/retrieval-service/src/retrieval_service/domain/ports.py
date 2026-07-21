from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from retrieval_service.domain.models import (
    Candidate,
    FormulatedQuery,
    RetrievalPack,
    RetrievalQuery,
)


@dataclass(frozen=True, slots=True)
class GenerationRef:
    id: UUID
    repository_id: UUID
    commit_sha: str


class GenerationPort(Protocol):
    async def resolve(
        self, repository_id: UUID, commit_sha: str, allow_ancestor: bool
    ) -> tuple[GenerationRef, bool]: ...


class LexicalSearchPort(Protocol):
    async def search(
        self, query: FormulatedQuery, request: RetrievalQuery, generation: GenerationRef, limit: int
    ) -> list[Candidate]: ...


class VectorSearchPort(Protocol):
    async def search(
        self, query: FormulatedQuery, request: RetrievalQuery, generation: GenerationRef, limit: int
    ) -> list[Candidate]: ...


class SymbolLookupPort(Protocol):
    async def search(
        self, query: FormulatedQuery, request: RetrievalQuery, generation: GenerationRef, limit: int
    ) -> list[Candidate]: ...


class GraphExpandPort(Protocol):
    async def expand(
        self, generation: GenerationRef, candidates: list[Candidate], node_budget: int
    ) -> list[Candidate]: ...


class RerankerPort(Protocol):
    async def rerank(
        self, query: str, candidates: list[Candidate], limit: int
    ) -> list[Candidate]: ...


class RetrievalPort(Protocol):
    async def retrieve(self, query: RetrievalQuery) -> RetrievalPack: ...
