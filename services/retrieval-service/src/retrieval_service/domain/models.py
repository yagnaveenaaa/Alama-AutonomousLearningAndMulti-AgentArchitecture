from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from alama_common.errors import ValidationError


class TrustLabel(StrEnum):
    REPOSITORY = "repository"
    DOCUMENTATION = "documentation"
    UNTRUSTED = "untrusted"


@dataclass(frozen=True, slots=True)
class RetrievalQuery:
    tenant_id: UUID
    repository_id: UUID
    commit_sha: str
    text: str
    acl_labels: frozenset[str]
    token_budget: int = 6000
    allow_ancestor_fallback: bool = False

    def __post_init__(self) -> None:
        if len(self.commit_sha) != 40:
            raise ValidationError("commit_sha must be 40 characters")
        if not self.text.strip():
            raise ValidationError("query text is required")
        if self.token_budget < 100:
            raise ValidationError("token_budget must be at least 100")


@dataclass(frozen=True, slots=True)
class FormulatedQuery:
    keyword_query: str
    semantic_query: str
    symbol_queries: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Candidate:
    evidence_id: UUID
    tenant_id: UUID
    repository_id: UUID
    generation_id: UUID
    commit_sha: str
    path: str
    start_line: int
    end_line: int
    content_sha: str
    text: str
    symbol: str | None
    language: str | None
    acl_labels: frozenset[str]
    trust_label: TrustLabel
    score: float


@dataclass(frozen=True, slots=True)
class Citation:
    evidence_id: UUID
    path: str
    start: int
    end: int
    commit: str
    sha: str


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    id: UUID
    path: str
    start_line: int
    end_line: int
    commit_sha: str
    content_sha: str
    content: str
    score: float
    trust_label: TrustLabel
    symbol: str | None
    language: str | None


@dataclass(frozen=True, slots=True)
class RetrievalPack:
    repository_id: UUID
    requested_commit_sha: str
    indexed_commit_sha: str
    generation_id: UUID
    stale: bool
    evidence: tuple[EvidenceItem, ...]
    citations: tuple[Citation, ...]
    estimated_tokens: int
