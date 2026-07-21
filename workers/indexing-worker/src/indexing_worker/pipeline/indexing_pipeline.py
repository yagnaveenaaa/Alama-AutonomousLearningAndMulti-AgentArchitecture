from __future__ import annotations

import hashlib
import re
from uuid import UUID

from alama_common.errors import DomainInvariantError
from alama_common.ids import new_uuid7

from indexing_worker.chunking.semantic_chunker import SemanticChunker
from indexing_worker.domain.classifier import RepoClassifier
from indexing_worker.domain.incremental import IncrementalDiffEngine
from indexing_worker.domain.models import (
    DependencyPackage,
    FileClassification,
    IndexGeneration,
    IndexGenerationStats,
    IndexJob,
    SourceFile,
    SymbolEdge,
    SymbolNode,
)
from indexing_worker.domain.ports import (
    Embedder,
    IndexMetaRepository,
    SnapshotSource,
    SnapshotStatusPort,
)
from indexing_worker.parsers.tree_sitter_facade import TreeSitterFacade
from indexing_worker.publishers.index_publisher import EmbeddingBatcher, IndexPublisher

_REQ_RE = re.compile(r"^([A-Za-z0-9_.\-]+)\s*(?:==|>=|<=|~=)?\s*([A-Za-z0-9_.\-]+)?")


class EnrichmentJoiner:
    """Join SCM metadata (owners/blame/CI) — stub joins for first slice (LLD §7.1)."""

    def enrich(self, files: list[SourceFile]) -> list[SourceFile]:
        return files


class IndexingPipeline:
    """Orchestrates stages classify → parse → enrich → chunk → embed → publish (LLD §2.14)."""

    def __init__(
        self,
        *,
        snapshots_source: SnapshotSource,
        snapshot_status: SnapshotStatusPort,
        meta: IndexMetaRepository,
        classifier: RepoClassifier,
        parser: TreeSitterFacade,
        chunker: SemanticChunker,
        enricher: EnrichmentJoiner,
        diff_engine: IncrementalDiffEngine,
        embedding_batcher: EmbeddingBatcher,
        publisher: IndexPublisher,
        embedder: Embedder,
        parent_manifest_loader: SnapshotSource | None = None,
    ) -> None:
        self._source = snapshots_source
        self._status = snapshot_status
        self._meta = meta
        self._classifier = classifier
        self._parser = parser
        self._chunker = chunker
        self._enricher = enricher
        self._diff = diff_engine
        self._batcher = embedding_batcher
        self._publisher = publisher
        self._embedder = embedder
        self._parent_loader = parent_manifest_loader or snapshots_source

    async def run(self, job: IndexJob) -> IndexGeneration:
        await self._status.mark_indexing(job.snapshot_id)
        generation = IndexGeneration.start_building(
            tenant_id=job.tenant_id,
            repository_id=job.repository_id,
            snapshot_id=job.snapshot_id,
            commit_sha=job.commit_sha,
            embedding_model=self._embedder.model_name,
            embedding_dim=self._embedder.dimension,
        )
        await self._meta.save_generation(generation)

        try:
            return await self._run_stages(job, generation)
        except Exception as exc:
            generation.fail(type(exc).__name__)
            await self._meta.save_generation(generation)
            await self._status.mark_failed(job.snapshot_id, type(exc).__name__)
            raise

    async def _run_stages(self, job: IndexJob, generation: IndexGeneration) -> IndexGeneration:
        manifest_ref = job.manifest_ref or f"snapshots/{job.repository_id}/{job.commit_sha}.json"
        manifest = await self._source.load_manifest(manifest_ref)

        parent_manifest = None
        if job.parent_commit_sha:
            parent_ref = f"snapshots/{job.repository_id}/{job.parent_commit_sha}.json"
            try:
                parent_manifest = await self._parent_loader.load_manifest(parent_ref)
            except Exception:
                parent_manifest = None

        diff = self._diff.diff(parent_manifest, manifest)
        stats = IndexGenerationStats(file_count=len(manifest.entries))

        files: list[SourceFile] = []
        for entry in manifest.entries:
            raw = await self._source.load_file(manifest_ref, entry.path)
            classified = self._classifier.classify_file(
                SourceFile(
                    path=raw.path,
                    content=raw.content,
                    content_hash=raw.content_hash or entry.content_hash,
                    language=entry.language or self._classifier.detect_language(entry.path),
                    classification=FileClassification.SOURCE,
                )
            )
            files.append(classified)

        files = self._enricher.enrich(files)

        all_nodes: list[SymbolNode] = []
        all_edges: list[SymbolEdge] = []
        all_chunks = []
        deps: list[DependencyPackage] = []

        for file in files:
            if file.classification == FileClassification.SKIP:
                stats.skipped_count += 1
                continue
            if file.classification in {
                FileClassification.BINARY,
                FileClassification.SECRET_HIT,
                FileClassification.VENDOR,
                FileClassification.GENERATED,
            }:
                stats.skipped_count += 1
                continue

            if file.language:
                stats.language_coverage[file.language] = (
                    stats.language_coverage.get(file.language, 0) + 1
                )

            if file.classification == FileClassification.SOURCE:
                stats.source_file_count += 1

            parse = self._parser.parse(
                file=file,
                tenant_id=job.tenant_id,
                repository_id=job.repository_id,
                generation_id=generation.id,
            )
            if (
                file.language
                and file.language not in {"python", "markdown", "config"}
                and not parse.nodes
            ):
                stats.unsupported_fallback_count += 1

            all_nodes.extend(parse.nodes)
            all_edges.extend(parse.edges)

            chunks = self._chunker.chunk_file(
                file=file,
                symbols=list(parse.nodes),
                tenant_id=job.tenant_id,
                repository_id=job.repository_id,
                generation_id=generation.id,
                commit_sha=job.commit_sha,
                embedding_model=self._embedder.model_name,
            )
            all_chunks.extend(chunks)

            if file.path.endswith("requirements.txt") or file.path.endswith("pyproject.toml"):
                deps.extend(self._extract_deps(file, generation.id))

        stats.symbol_count = len(all_nodes)
        stats.edge_count = len(all_edges)
        stats.chunk_count = len(all_chunks)

        embedded = await self._batcher.embed(all_chunks)
        stats.embedded_count = len(embedded)

        await self._meta.save_dependencies(deps)

        return await self._publisher.publish(
            generation=generation,
            nodes=all_nodes,
            edges=all_edges,
            embedded=embedded,
            stats=stats,
            removed_paths=sorted({e.path for e in diff.removed}),
        )

    def _extract_deps(self, file: SourceFile, generation_id: UUID) -> list[DependencyPackage]:
        packages: list[DependencyPackage] = []
        if file.path.endswith("requirements.txt"):
            for line in file.content.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                match = _REQ_RE.match(line)
                if not match:
                    continue
                packages.append(
                    DependencyPackage(
                        id=new_uuid7(),
                        generation_id=generation_id,
                        ecosystem="pypi",
                        name=match.group(1),
                        version=match.group(2) or "",
                        path=file.path,
                    )
                )
        return packages


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def require_commit_sha(sha: str) -> str:
    if len(sha) != 40:
        raise DomainInvariantError("commit_sha must be 40 hex characters")
    return sha.lower()
