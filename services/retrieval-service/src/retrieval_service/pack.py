from __future__ import annotations

from retrieval_service.domain.models import (
    Candidate,
    Citation,
    EvidenceItem,
    RetrievalPack,
    RetrievalQuery,
)
from retrieval_service.domain.ports import GenerationRef


class ContextPacker:
    """Allocate token budget while preserving evidence boundaries."""

    def pack(
        self,
        *,
        request: RetrievalQuery,
        generation: GenerationRef,
        stale: bool,
        candidates: list[Candidate],
    ) -> RetrievalPack:
        used = 0
        evidence: list[EvidenceItem] = []
        citations: list[Citation] = []
        for candidate in candidates:
            tokens = max(1, len(candidate.text) // 4)
            if used + tokens > request.token_budget:
                continue
            used += tokens
            evidence.append(
                EvidenceItem(
                    id=candidate.evidence_id,
                    path=candidate.path,
                    start_line=candidate.start_line,
                    end_line=candidate.end_line,
                    commit_sha=candidate.commit_sha,
                    content_sha=candidate.content_sha,
                    content=candidate.text,
                    score=candidate.score,
                    trust_label=candidate.trust_label,
                    symbol=candidate.symbol,
                    language=candidate.language,
                )
            )
            citations.append(
                Citation(
                    evidence_id=candidate.evidence_id,
                    path=candidate.path,
                    start=candidate.start_line,
                    end=candidate.end_line,
                    commit=candidate.commit_sha,
                    sha=candidate.content_sha,
                )
            )
        return RetrievalPack(
            repository_id=request.repository_id,
            requested_commit_sha=request.commit_sha,
            indexed_commit_sha=generation.commit_sha,
            generation_id=generation.id,
            stale=stale,
            evidence=tuple(evidence),
            citations=tuple(citations),
            estimated_tokens=used,
        )
