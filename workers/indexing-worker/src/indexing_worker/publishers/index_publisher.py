from __future__ import annotations

from indexing_worker.domain.models import (
    Chunk,
    EmbeddedChunk,
    IndexGeneration,
    IndexGenerationStats,
    SymbolEdge,
    SymbolNode,
)
from indexing_worker.domain.ports import (
    Embedder,
    IndexMetaRepository,
    LexicalIndexWriter,
    SnapshotStatusPort,
    VectorIndexWriter,
)


class IndexPublisher:
    """Two-phase publish: building → validating → activate (LLD §2.14 / §7.1)."""

    def __init__(
        self,
        meta: IndexMetaRepository,
        vectors: VectorIndexWriter,
        lexical: LexicalIndexWriter,
        snapshots: SnapshotStatusPort,
    ) -> None:
        self._meta = meta
        self._vectors = vectors
        self._lexical = lexical
        self._snapshots = snapshots

    async def publish(
        self,
        *,
        generation: IndexGeneration,
        nodes: list[SymbolNode],
        edges: list[SymbolEdge],
        embedded: list[EmbeddedChunk],
        stats: IndexGenerationStats,
        removed_paths: list[str],
    ) -> IndexGeneration:
        await self._meta.save_symbols(nodes, edges)
        chunks = [item.chunk for item in embedded]
        await self._vectors.upsert(namespace=generation.vector_namespace, items=embedded)
        await self._lexical.upsert(index_name=generation.lexical_index_name, chunks=chunks)
        if removed_paths:
            await self._vectors.tombstone_paths(
                namespace=generation.vector_namespace,
                paths=removed_paths,
            )
            await self._lexical.tombstone_paths(
                index_name=generation.lexical_index_name,
                paths=removed_paths,
            )

        generation.mark_validating(stats)
        await self._meta.save_generation(generation)

        previous = await self._meta.get_active(generation.repository_id)
        if previous is not None and previous.id != generation.id:
            previous.retire()
            await self._meta.save_generation(previous)

        generation.activate()
        await self._meta.save_generation(generation)
        await self._snapshots.mark_ready(generation.snapshot_id, generation.id)
        return generation


class EmbeddingBatcher:
    """Batch embeddings via Model Gateway port; dedupe by content_hash (LLD §7.4)."""

    def __init__(self, embedder: Embedder) -> None:
        self._embedder = embedder

    async def embed(self, chunks: list[Chunk]) -> list[EmbeddedChunk]:
        if not chunks:
            return []

        unique_texts: list[str] = []
        hash_to_index: dict[str, int] = {}
        for chunk in chunks:
            if chunk.content_hash not in hash_to_index:
                hash_to_index[chunk.content_hash] = len(unique_texts)
                unique_texts.append(chunk.text)

        vectors = await self._embedder.embed_batch(unique_texts)
        result: list[EmbeddedChunk] = []
        for chunk in chunks:
            idx = hash_to_index[chunk.content_hash]
            result.append(EmbeddedChunk(chunk=chunk, vector=vectors[idx]))
        return result
