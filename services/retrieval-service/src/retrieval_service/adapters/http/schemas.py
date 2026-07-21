from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class RetrieveRequest(BaseModel):
    repository_id: UUID
    commit_sha: str = Field(min_length=40, max_length=40)
    query: str = Field(min_length=1, max_length=20_000)
    acl_labels: list[str] = Field(default_factory=list)
    token_budget: int = Field(default=6000, ge=100, le=100_000)
    allow_ancestor_fallback: bool = False


class CitationResponse(BaseModel):
    evidence_id: UUID
    path: str
    start: int
    end: int
    commit: str
    sha: str


class EvidenceResponse(BaseModel):
    id: UUID
    path: str
    start_line: int
    end_line: int
    commit_sha: str
    content_sha: str
    content: str
    score: float
    trust_label: str
    symbol: str | None
    language: str | None


class RetrievalPackResponse(BaseModel):
    repository_id: UUID
    requested_commit_sha: str
    indexed_commit_sha: str
    generation_id: UUID
    stale: bool
    evidence: list[EvidenceResponse]
    citations: list[CitationResponse]
    estimated_tokens: int
