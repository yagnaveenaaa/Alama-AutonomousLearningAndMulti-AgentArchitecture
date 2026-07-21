from __future__ import annotations

import math
import re
from dataclasses import replace
from uuid import UUID

from alama_common.errors import PreconditionFailedError

from retrieval_service.domain.models import Candidate, FormulatedQuery, RetrievalQuery
from retrieval_service.domain.ports import GenerationRef


class InMemoryRetrievalIndex:
    """Local managed-vector/OpenSearch/index_meta stand-in."""

    def __init__(self) -> None:
        self.generations: dict[UUID, GenerationRef] = {}
        self.active_by_repository: dict[UUID, UUID] = {}
        self.chunks: dict[UUID, list[Candidate]] = {}
        self.adjacency: dict[UUID, set[UUID]] = {}

    def add_generation(
        self, generation: GenerationRef, candidates: list[Candidate], *, active: bool = True
    ) -> None:
        self.generations[generation.id] = generation
        self.chunks[generation.id] = list(candidates)
        if active:
            self.active_by_repository[generation.repository_id] = generation.id

    def connect(self, left: UUID, right: UUID) -> None:
        self.adjacency.setdefault(left, set()).add(right)
        self.adjacency.setdefault(right, set()).add(left)


class InMemoryGenerationAdapter:
    def __init__(self, index: InMemoryRetrievalIndex) -> None:
        self._index = index

    async def resolve(
        self, repository_id: UUID, commit_sha: str, allow_ancestor: bool
    ) -> tuple[GenerationRef, bool]:
        exact = next(
            (
                generation
                for generation in self._index.generations.values()
                if generation.repository_id == repository_id
                and generation.commit_sha == commit_sha.lower()
            ),
            None,
        )
        if exact is not None:
            return exact, False
        if allow_ancestor:
            active_id = self._index.active_by_repository.get(repository_id)
            if active_id is not None:
                return self._index.generations[active_id], True
        raise PreconditionFailedError(
            "Requested commit is not indexed",
            details={"repository_id": str(repository_id), "commit_sha": commit_sha},
        )


class InMemorySearchAdapter:
    def __init__(self, index: InMemoryRetrievalIndex) -> None:
        self._index = index

    def _visible(self, generation: GenerationRef, request: RetrievalQuery) -> list[Candidate]:
        return [
            item
            for item in self._index.chunks.get(generation.id, [])
            if item.tenant_id == request.tenant_id
            and (not item.acl_labels or item.acl_labels <= request.acl_labels)
        ]

    async def search_lexical(
        self, query: FormulatedQuery, request: RetrievalQuery, generation: GenerationRef, limit: int
    ) -> list[Candidate]:
        terms = set(re.findall(r"[a-z0-9_]+", query.keyword_query.lower()))
        scored = []
        for item in self._visible(generation, request):
            searchable = f"{item.path} {item.symbol or ''} {item.text}".lower()
            words = re.findall(r"[a-z0-9_]+", searchable)
            score = sum(words.count(term) for term in terms) / max(1.0, math.sqrt(len(words)))
            if score:
                scored.append(replace(item, score=score))
        return sorted(scored, key=lambda item: item.score, reverse=True)[:limit]

    async def search_vector(
        self, query: FormulatedQuery, request: RetrievalQuery, generation: GenerationRef, limit: int
    ) -> list[Candidate]:
        terms = set(re.findall(r"[a-z0-9_]+", query.semantic_query.lower()))
        scored = []
        for item in self._visible(generation, request):
            item_terms = set(re.findall(r"[a-z0-9_]+", item.text.lower()))
            union = terms | item_terms
            score = len(terms & item_terms) / len(union) if union else 0.0
            if score:
                scored.append(replace(item, score=score))
        return sorted(scored, key=lambda item: item.score, reverse=True)[:limit]

    async def search_symbol(
        self, query: FormulatedQuery, request: RetrievalQuery, generation: GenerationRef, limit: int
    ) -> list[Candidate]:
        names = {name.lower() for name in query.symbol_queries}
        found = [
            replace(item, score=1.0)
            for item in self._visible(generation, request)
            if item.symbol and any(name in item.symbol.lower() for name in names)
        ]
        return found[:limit]


class LexicalAdapter:
    def __init__(self, search: InMemorySearchAdapter) -> None:
        self._search = search

    async def search(
        self, query: FormulatedQuery, request: RetrievalQuery, generation: GenerationRef, limit: int
    ) -> list[Candidate]:
        return await self._search.search_lexical(query, request, generation, limit)


class VectorAdapter:
    def __init__(self, search: InMemorySearchAdapter) -> None:
        self._search = search

    async def search(
        self, query: FormulatedQuery, request: RetrievalQuery, generation: GenerationRef, limit: int
    ) -> list[Candidate]:
        return await self._search.search_vector(query, request, generation, limit)


class SymbolAdapter:
    def __init__(self, search: InMemorySearchAdapter) -> None:
        self._search = search

    async def search(
        self, query: FormulatedQuery, request: RetrievalQuery, generation: GenerationRef, limit: int
    ) -> list[Candidate]:
        return await self._search.search_symbol(query, request, generation, limit)


class InMemoryGraphAdapter:
    def __init__(self, index: InMemoryRetrievalIndex) -> None:
        self._index = index

    async def expand(
        self, generation: GenerationRef, candidates: list[Candidate], node_budget: int
    ) -> list[Candidate]:
        by_id = {item.evidence_id: item for item in self._index.chunks.get(generation.id, [])}
        result = list(candidates)
        seen = {item.evidence_id for item in candidates}
        for item in candidates:
            for neighbour_id in self._index.adjacency.get(item.evidence_id, set()):
                if neighbour_id not in seen and neighbour_id in by_id and len(result) < node_budget:
                    result.append(replace(by_id[neighbour_id], score=item.score * 0.8))
                    seen.add(neighbour_id)
        return result


class DeterministicReranker:
    """Local Model Gateway reranker adapter."""

    async def rerank(self, query: str, candidates: list[Candidate], limit: int) -> list[Candidate]:
        terms = set(re.findall(r"[a-z0-9_]+", query.lower()))
        reranked = [
            replace(
                item,
                score=item.score
                + 0.01 * len(terms & set(re.findall(r"[a-z0-9_]+", item.text.lower()))),
            )
            for item in candidates
        ]
        return sorted(reranked, key=lambda item: item.score, reverse=True)[:limit]
