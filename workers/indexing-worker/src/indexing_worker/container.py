from __future__ import annotations

from dataclasses import dataclass

from indexing_worker.adapters.persistence.memory import (
    DeterministicEmbedder,
    InMemoryIndexMetaRepository,
    InMemoryIndexMetaStore,
    InMemoryJobQueue,
    InMemoryLexicalIndex,
    InMemorySnapshotSource,
    InMemorySnapshotStatus,
    InMemoryVectorIndex,
)
from indexing_worker.chunking.semantic_chunker import SemanticChunker
from indexing_worker.config import IndexingWorkerSettings
from indexing_worker.domain.classifier import RepoClassifier
from indexing_worker.domain.incremental import IncrementalDiffEngine
from indexing_worker.parsers.tree_sitter_facade import TreeSitterFacade
from indexing_worker.pipeline.indexing_pipeline import EnrichmentJoiner, IndexingPipeline
from indexing_worker.publishers.index_publisher import EmbeddingBatcher, IndexPublisher


@dataclass
class IndexingWorkerContainer:
    settings: IndexingWorkerSettings
    store: InMemoryIndexMetaStore
    meta: InMemoryIndexMetaRepository
    snapshot_source: InMemorySnapshotSource
    snapshot_status: InMemorySnapshotStatus
    queue: InMemoryJobQueue
    vectors: InMemoryVectorIndex
    lexical: InMemoryLexicalIndex
    embedder: DeterministicEmbedder
    pipeline: IndexingPipeline


def build_container(settings: IndexingWorkerSettings | None = None) -> IndexingWorkerContainer:
    settings = settings or IndexingWorkerSettings()
    supported = frozenset(
        lang.strip() for lang in settings.supported_languages.split(",") if lang.strip()
    )
    store = InMemoryIndexMetaStore()
    meta = InMemoryIndexMetaRepository(store)
    snapshot_source = InMemorySnapshotSource()
    snapshot_status = InMemorySnapshotStatus(store)
    queue = InMemoryJobQueue()
    vectors = InMemoryVectorIndex()
    lexical = InMemoryLexicalIndex()
    embedder = DeterministicEmbedder(
        model_name=settings.embedding_model,
        dimension=settings.embedding_dim,
    )
    publisher = IndexPublisher(meta, vectors, lexical, snapshot_status)
    pipeline = IndexingPipeline(
        snapshots_source=snapshot_source,
        snapshot_status=snapshot_status,
        meta=meta,
        classifier=RepoClassifier(supported_languages=supported),
        parser=TreeSitterFacade(supported_languages=supported),
        chunker=SemanticChunker(max_chunk_tokens=settings.max_chunk_tokens),
        enricher=EnrichmentJoiner(),
        diff_engine=IncrementalDiffEngine(),
        embedding_batcher=EmbeddingBatcher(embedder),
        publisher=publisher,
        embedder=embedder,
    )
    return IndexingWorkerContainer(
        settings=settings,
        store=store,
        meta=meta,
        snapshot_source=snapshot_source,
        snapshot_status=snapshot_status,
        queue=queue,
        vectors=vectors,
        lexical=lexical,
        embedder=embedder,
        pipeline=pipeline,
    )
