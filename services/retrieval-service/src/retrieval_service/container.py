from __future__ import annotations

from dataclasses import dataclass

from retrieval_service.adapters.memory import (
    DeterministicReranker,
    InMemoryGenerationAdapter,
    InMemoryGraphAdapter,
    InMemoryRetrievalIndex,
    InMemorySearchAdapter,
    LexicalAdapter,
    SymbolAdapter,
    VectorAdapter,
)
from retrieval_service.fusion import ReciprocalRankFusion
from retrieval_service.pack import ContextPacker
from retrieval_service.query import QueryFormulator
from retrieval_service.search import HybridRetriever


@dataclass
class RetrievalContainer:
    index: InMemoryRetrievalIndex
    retriever: HybridRetriever


def build_container() -> RetrievalContainer:
    index = InMemoryRetrievalIndex()
    search = InMemorySearchAdapter(index)
    retriever = HybridRetriever(
        generations=InMemoryGenerationAdapter(index),
        lexical=LexicalAdapter(search),
        vector=VectorAdapter(search),
        symbols=SymbolAdapter(search),
        graph=InMemoryGraphAdapter(index),
        reranker=DeterministicReranker(),
        formulator=QueryFormulator(),
        fusion=ReciprocalRankFusion(),
        packer=ContextPacker(),
    )
    return RetrievalContainer(index=index, retriever=retriever)
