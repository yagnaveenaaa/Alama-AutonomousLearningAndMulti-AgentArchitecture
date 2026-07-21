from __future__ import annotations

import asyncio

from retrieval_service.domain.models import Candidate, RetrievalPack, RetrievalQuery
from retrieval_service.domain.ports import (
    GenerationPort,
    GraphExpandPort,
    LexicalSearchPort,
    RerankerPort,
    SymbolLookupPort,
    VectorSearchPort,
)
from retrieval_service.fusion import ReciprocalRankFusion
from retrieval_service.pack import ContextPacker
from retrieval_service.query import QueryFormulator


class HybridRetriever:
    """Commit-consistent hybrid retrieval orchestration (LLD §2.7 / §9.3)."""

    def __init__(
        self,
        *,
        generations: GenerationPort,
        lexical: LexicalSearchPort,
        vector: VectorSearchPort,
        symbols: SymbolLookupPort,
        graph: GraphExpandPort,
        reranker: RerankerPort,
        formulator: QueryFormulator,
        fusion: ReciprocalRankFusion,
        packer: ContextPacker,
    ) -> None:
        self._generations = generations
        self._lexical = lexical
        self._vector = vector
        self._symbols = symbols
        self._graph = graph
        self._reranker = reranker
        self._formulator = formulator
        self._fusion = fusion
        self._packer = packer

    async def retrieve(self, request: RetrievalQuery) -> RetrievalPack:
        generation, stale = await self._generations.resolve(
            request.repository_id, request.commit_sha, request.allow_ancestor_fallback
        )
        query = self._formulator.formulate(request.text)
        lexical, dense, symbols = await asyncio.gather(
            self._lexical.search(query, request, generation, 50),
            self._vector.search(query, request, generation, 50),
            self._symbols.search(query, request, generation, 50),
        )
        fused = self._fusion.fuse(symbol=symbols, lexical=lexical, dense=dense)
        authorized = self._authorize(fused, request)
        expanded = await self._graph.expand(generation, authorized[:50], 20)
        reranked = await self._reranker.rerank(request.text, self._authorize(expanded, request), 12)
        return self._packer.pack(
            request=request,
            generation=generation,
            stale=stale,
            candidates=self._authorize(reranked, request),
        )

    @staticmethod
    def _authorize(candidates: list[Candidate], request: RetrievalQuery) -> list[Candidate]:
        return [
            item
            for item in candidates
            if item.tenant_id == request.tenant_id
            and item.repository_id == request.repository_id
            and (not item.acl_labels or item.acl_labels <= request.acl_labels)
        ]
