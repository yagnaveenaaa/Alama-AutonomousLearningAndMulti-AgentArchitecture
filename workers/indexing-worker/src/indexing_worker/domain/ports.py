from __future__ import annotations

from typing import Protocol
from uuid import UUID

from indexing_worker.domain.models import (
    Chunk,
    DependencyPackage,
    EmbeddedChunk,
    IndexGeneration,
    IndexJob,
    SnapshotManifest,
    SourceFile,
    SymbolEdge,
    SymbolNode,
)


class SnapshotSource(Protocol):
    """Load snapshot manifests and file contents from object storage."""

    async def load_manifest(self, manifest_ref: str) -> SnapshotManifest: ...

    async def load_file(self, manifest_ref: str, path: str) -> SourceFile: ...


class Embedder(Protocol):
    """Narrow port to Model Gateway embeddings (LLD §2.14 / SOLID I)."""

    @property
    def model_name(self) -> str: ...

    @property
    def dimension(self) -> int: ...

    async def embed_batch(self, texts: list[str]) -> list[tuple[float, ...]]: ...


class VectorIndexWriter(Protocol):
    async def upsert(
        self,
        *,
        namespace: str,
        items: list[EmbeddedChunk],
    ) -> None: ...

    async def tombstone_paths(
        self,
        *,
        namespace: str,
        paths: list[str],
    ) -> None: ...


class LexicalIndexWriter(Protocol):
    async def upsert(
        self,
        *,
        index_name: str,
        chunks: list[Chunk],
    ) -> None: ...

    async def tombstone_paths(
        self,
        *,
        index_name: str,
        paths: list[str],
    ) -> None: ...


class IndexMetaRepository(Protocol):
    async def save_generation(self, generation: IndexGeneration) -> None: ...

    async def get_active(self, repository_id: UUID) -> IndexGeneration | None: ...

    async def get_generation(self, generation_id: UUID) -> IndexGeneration | None: ...

    async def save_symbols(
        self,
        nodes: list[SymbolNode],
        edges: list[SymbolEdge],
    ) -> None: ...

    async def save_dependencies(self, packages: list[DependencyPackage]) -> None: ...

    async def list_symbols(self, generation_id: UUID) -> list[SymbolNode]: ...

    async def list_edges(self, generation_id: UUID) -> list[SymbolEdge]: ...


class SnapshotStatusPort(Protocol):
    """Notify repository-service of snapshot index outcome (app-enforced cross-DB)."""

    async def mark_indexing(self, snapshot_id: UUID) -> None: ...

    async def mark_ready(self, snapshot_id: UUID, index_generation_id: UUID) -> None: ...

    async def mark_failed(self, snapshot_id: UUID, error_code: str) -> None: ...


class IndexJobQueue(Protocol):
    async def enqueue(self, job: IndexJob) -> None: ...

    async def dequeue(self) -> IndexJob | None: ...
