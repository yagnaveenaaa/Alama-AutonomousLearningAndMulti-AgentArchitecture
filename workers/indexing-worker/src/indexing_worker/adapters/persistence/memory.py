from __future__ import annotations

import hashlib
import math
from collections import defaultdict
from uuid import UUID

from alama_common.errors import NotFoundError

from indexing_worker.domain.models import (
    Chunk,
    DependencyPackage,
    EmbeddedChunk,
    FileClassification,
    IndexGeneration,
    IndexGenerationState,
    IndexJob,
    ManifestEntry,
    SnapshotManifest,
    SourceFile,
    SymbolEdge,
    SymbolNode,
)


class InMemoryIndexMetaStore:
    def __init__(self) -> None:
        self.generations: dict[UUID, IndexGeneration] = {}
        self.symbols: dict[UUID, list[SymbolNode]] = defaultdict(list)
        self.edges: dict[UUID, list[SymbolEdge]] = defaultdict(list)
        self.dependencies: dict[UUID, list[DependencyPackage]] = defaultdict(list)
        self.snapshot_states: dict[UUID, tuple[str, UUID | None, str | None]] = {}


class InMemoryIndexMetaRepository:
    def __init__(self, store: InMemoryIndexMetaStore) -> None:
        self._store = store

    async def save_generation(self, generation: IndexGeneration) -> None:
        self._store.generations[generation.id] = generation

    async def get_active(self, repository_id: UUID) -> IndexGeneration | None:
        for gen in self._store.generations.values():
            if gen.repository_id == repository_id and gen.state == IndexGenerationState.ACTIVE:
                return gen
        return None

    async def get_generation(self, generation_id: UUID) -> IndexGeneration | None:
        return self._store.generations.get(generation_id)

    async def save_symbols(
        self,
        nodes: list[SymbolNode],
        edges: list[SymbolEdge],
    ) -> None:
        for node in nodes:
            self._store.symbols[node.generation_id].append(node)
        for edge in edges:
            self._store.edges[edge.generation_id].append(edge)

    async def save_dependencies(self, packages: list[DependencyPackage]) -> None:
        for pkg in packages:
            self._store.dependencies[pkg.generation_id].append(pkg)

    async def list_symbols(self, generation_id: UUID) -> list[SymbolNode]:
        return list(self._store.symbols.get(generation_id, []))

    async def list_edges(self, generation_id: UUID) -> list[SymbolEdge]:
        return list(self._store.edges.get(generation_id, []))


class InMemorySnapshotStatus:
    def __init__(self, store: InMemoryIndexMetaStore) -> None:
        self._store = store

    async def mark_indexing(self, snapshot_id: UUID) -> None:
        self._store.snapshot_states[snapshot_id] = ("indexing", None, None)

    async def mark_ready(self, snapshot_id: UUID, index_generation_id: UUID) -> None:
        self._store.snapshot_states[snapshot_id] = ("ready", index_generation_id, None)

    async def mark_failed(self, snapshot_id: UUID, error_code: str) -> None:
        self._store.snapshot_states[snapshot_id] = ("failed", None, error_code)


class InMemorySnapshotSource:
    """Local object-store stand-in keyed by manifest_ref."""

    def __init__(self) -> None:
        self._manifests: dict[str, SnapshotManifest] = {}
        self._files: dict[str, dict[str, SourceFile]] = defaultdict(dict)

    def put_snapshot(
        self,
        *,
        manifest_ref: str,
        repository_id: UUID,
        commit_sha: str,
        parent_commit_sha: str | None,
        files: dict[str, str],
    ) -> SnapshotManifest:
        clean: dict[str, SourceFile] = {}
        clean_entries: list[ManifestEntry] = []
        for path, content in files.items():
            digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
            language: str | None = None
            if path.endswith(".py"):
                language = "python"
            elif path.endswith(".md"):
                language = "markdown"
            clean_entries.append(
                ManifestEntry(
                    path=path,
                    content_hash=digest,
                    size_bytes=len(content.encode("utf-8")),
                    language=language,
                )
            )
            clean[path] = SourceFile(
                path=path,
                content=content,
                content_hash=digest,
                language=language,
                classification=FileClassification.SOURCE,
            )
        manifest = SnapshotManifest(
            repository_id=repository_id,
            commit_sha=commit_sha,
            parent_commit_sha=parent_commit_sha,
            entries=tuple(clean_entries),
        )
        self._manifests[manifest_ref] = manifest
        self._files[manifest_ref] = clean
        return manifest

    async def load_manifest(self, manifest_ref: str) -> SnapshotManifest:
        manifest = self._manifests.get(manifest_ref)
        if manifest is None:
            raise NotFoundError(f"Manifest not found: {manifest_ref}")
        return manifest

    async def load_file(self, manifest_ref: str, path: str) -> SourceFile:
        files = self._files.get(manifest_ref, {})
        file = files.get(path)
        if file is None:
            raise NotFoundError(f"File not found: {path}")
        return file


class InMemoryVectorIndex:
    def __init__(self) -> None:
        self.namespaces: dict[str, list[EmbeddedChunk]] = defaultdict(list)
        self.tombstones: dict[str, set[str]] = defaultdict(set)

    async def upsert(self, *, namespace: str, items: list[EmbeddedChunk]) -> None:
        self.namespaces[namespace].extend(items)

    async def tombstone_paths(self, *, namespace: str, paths: list[str]) -> None:
        self.tombstones[namespace].update(paths)


class InMemoryLexicalIndex:
    def __init__(self) -> None:
        self.indexes: dict[str, list[Chunk]] = defaultdict(list)
        self.tombstones: dict[str, set[str]] = defaultdict(set)

    async def upsert(self, *, index_name: str, chunks: list[Chunk]) -> None:
        self.indexes[index_name].extend(chunks)

    async def tombstone_paths(self, *, index_name: str, paths: list[str]) -> None:
        self.tombstones[index_name].update(paths)


class InMemoryJobQueue:
    def __init__(self) -> None:
        self._jobs: list[IndexJob] = []

    async def enqueue(self, job: IndexJob) -> None:
        self._jobs.append(job)

    async def dequeue(self) -> IndexJob | None:
        if not self._jobs:
            return None
        return self._jobs.pop(0)


class DeterministicEmbedder:
    """Local stand-in for Model Gateway embeddings (same model+dim per generation)."""

    def __init__(self, *, model_name: str, dimension: int) -> None:
        self._model_name = model_name
        self._dimension = dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed_batch(self, texts: list[str]) -> list[tuple[float, ...]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> tuple[float, ...]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values: list[float] = []
        for i in range(self._dimension):
            byte = digest[i % len(digest)]
            values.append((byte / 255.0) * 2.0 - 1.0)
        norm = math.sqrt(sum(v * v for v in values)) or 1.0
        return tuple(v / norm for v in values)
