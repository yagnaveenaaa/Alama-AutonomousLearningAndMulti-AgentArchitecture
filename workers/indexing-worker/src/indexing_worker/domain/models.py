from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from alama_common.errors import ConflictError, DomainInvariantError, ValidationError
from alama_common.ids import new_uuid7


class IndexGenerationState(StrEnum):
    BUILDING = "building"
    VALIDATING = "validating"
    ACTIVE = "active"
    RETIRED = "retired"
    FAILED = "failed"


class SymbolKind(StrEnum):
    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"


class EdgeType(StrEnum):
    CALLS = "calls"
    IMPORTS = "imports"
    INHERITS = "inherits"
    REFERENCES = "references"
    TESTS = "tests"


class ChunkKind(StrEnum):
    SYMBOL = "symbol"
    SECTION = "section"
    FILE = "file"
    LINE_WINDOW = "line_window"


class FileClassification(StrEnum):
    SOURCE = "source"
    DOC = "doc"
    CONFIG = "config"
    GENERATED = "generated"
    VENDOR = "vendor"
    BINARY = "binary"
    SECRET_HIT = "secret_hit"
    SKIP = "skip"


@dataclass(frozen=True, slots=True)
class ManifestEntry:
    path: str
    content_hash: str
    size_bytes: int
    language: str | None = None

    def __post_init__(self) -> None:
        if not self.path.strip():
            raise ValidationError("manifest path is required")
        if not self.content_hash.strip():
            raise ValidationError("content_hash is required")


@dataclass(frozen=True, slots=True)
class SnapshotManifest:
    """File tree + content hashes for a commit (object-store manifest)."""

    repository_id: UUID
    commit_sha: str
    parent_commit_sha: str | None
    entries: tuple[ManifestEntry, ...]

    def __post_init__(self) -> None:
        if len(self.commit_sha) != 40:
            raise DomainInvariantError("commit_sha must be 40 hex characters")

    def by_path(self) -> dict[str, ManifestEntry]:
        return {e.path: e for e in self.entries}


@dataclass(frozen=True, slots=True)
class SourceFile:
    path: str
    content: str
    content_hash: str
    language: str | None
    classification: FileClassification


@dataclass(frozen=True, slots=True)
class SymbolNode:
    id: UUID
    tenant_id: UUID
    repository_id: UUID
    generation_id: UUID
    language: str
    kind: SymbolKind
    name: str
    qualified_name: str
    path: str
    start_line: int
    end_line: int
    content_hash: str


@dataclass(frozen=True, slots=True)
class SymbolEdge:
    id: UUID
    generation_id: UUID
    src_symbol_id: UUID
    dst_symbol_id: UUID
    edge_type: EdgeType


@dataclass(frozen=True, slots=True)
class Chunk:
    id: UUID
    tenant_id: UUID
    repository_id: UUID
    generation_id: UUID
    commit_sha: str
    path: str
    symbol: str | None
    language: str | None
    acl_labels: tuple[str, ...]
    classification: FileClassification
    content_hash: str
    embedding_model: str
    chunk_kind: ChunkKind
    text: str
    start_line: int
    end_line: int
    parent_qualified_name: str | None = None


@dataclass(frozen=True, slots=True)
class EmbeddedChunk:
    chunk: Chunk
    vector: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class DependencyPackage:
    id: UUID
    generation_id: UUID
    ecosystem: str
    name: str
    version: str
    path: str


@dataclass
class IndexGenerationStats:
    file_count: int = 0
    source_file_count: int = 0
    symbol_count: int = 0
    edge_count: int = 0
    chunk_count: int = 0
    embedded_count: int = 0
    skipped_count: int = 0
    language_coverage: dict[str, int] = field(default_factory=dict)
    unsupported_fallback_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_count": self.file_count,
            "source_file_count": self.source_file_count,
            "symbol_count": self.symbol_count,
            "edge_count": self.edge_count,
            "chunk_count": self.chunk_count,
            "embedded_count": self.embedded_count,
            "skipped_count": self.skipped_count,
            "language_coverage": dict(self.language_coverage),
            "unsupported_fallback_count": self.unsupported_fallback_count,
        }


class IndexGeneration:
    """Index generation lifecycle (LLD §4.7 index_generations)."""

    def __init__(
        self,
        *,
        id: UUID,
        tenant_id: UUID,
        repository_id: UUID,
        snapshot_id: UUID,
        commit_sha: str,
        state: IndexGenerationState,
        embedding_model: str,
        embedding_dim: int,
        vector_namespace: str,
        lexical_index_name: str,
        stats: IndexGenerationStats,
        created_at: datetime,
        updated_at: datetime,
        activated_at: datetime | None = None,
        error_code: str | None = None,
    ) -> None:
        if len(commit_sha) != 40:
            raise DomainInvariantError("commit_sha must be 40 hex characters")
        self.id = id
        self.tenant_id = tenant_id
        self.repository_id = repository_id
        self.snapshot_id = snapshot_id
        self.commit_sha = commit_sha.lower()
        self.state = state
        self.embedding_model = embedding_model
        self.embedding_dim = embedding_dim
        self.vector_namespace = vector_namespace
        self.lexical_index_name = lexical_index_name
        self.stats = stats
        self.created_at = created_at
        self.updated_at = updated_at
        self.activated_at = activated_at
        self.error_code = error_code

    @classmethod
    def start_building(
        cls,
        *,
        tenant_id: UUID,
        repository_id: UUID,
        snapshot_id: UUID,
        commit_sha: str,
        embedding_model: str,
        embedding_dim: int,
    ) -> IndexGeneration:
        generation_id = new_uuid7()
        now = datetime.now(UTC)
        return cls(
            id=generation_id,
            tenant_id=tenant_id,
            repository_id=repository_id,
            snapshot_id=snapshot_id,
            commit_sha=commit_sha,
            state=IndexGenerationState.BUILDING,
            embedding_model=embedding_model,
            embedding_dim=embedding_dim,
            vector_namespace=f"vec:{repository_id}:{generation_id}",
            lexical_index_name=f"lex:{repository_id}:{generation_id}",
            stats=IndexGenerationStats(),
            created_at=now,
            updated_at=now,
        )

    def mark_validating(self, stats: IndexGenerationStats) -> None:
        if self.state != IndexGenerationState.BUILDING:
            raise ConflictError("Generation is not building")
        self.stats = stats
        self.state = IndexGenerationState.VALIDATING
        self.updated_at = datetime.now(UTC)

    def activate(self) -> None:
        if self.state != IndexGenerationState.VALIDATING:
            raise ConflictError("Generation is not validating")
        now = datetime.now(UTC)
        self.state = IndexGenerationState.ACTIVE
        self.activated_at = now
        self.updated_at = now

    def retire(self) -> None:
        if self.state != IndexGenerationState.ACTIVE:
            raise ConflictError("Only active generations can be retired")
        self.state = IndexGenerationState.RETIRED
        self.updated_at = datetime.now(UTC)

    def fail(self, error_code: str) -> None:
        self.state = IndexGenerationState.FAILED
        self.error_code = error_code
        self.updated_at = datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class IndexJob:
    """Queue message: snapshot ready for indexing (from repository outbox)."""

    tenant_id: UUID
    repository_id: UUID
    snapshot_id: UUID
    commit_sha: str
    parent_commit_sha: str | None = None
    manifest_ref: str = ""
