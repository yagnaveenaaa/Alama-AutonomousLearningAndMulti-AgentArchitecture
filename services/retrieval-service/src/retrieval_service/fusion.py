from __future__ import annotations

from dataclasses import replace

from retrieval_service.domain.models import Candidate


class ReciprocalRankFusion:
    """Weighted RRF; symbol > lexical > dense (LLD §9.3)."""

    def __init__(self, *, k: int = 60) -> None:
        self._k = k

    def fuse(
        self,
        *,
        symbol: list[Candidate],
        lexical: list[Candidate],
        dense: list[Candidate],
    ) -> list[Candidate]:
        scores: dict[object, float] = {}
        candidates: dict[object, Candidate] = {}
        for weight, ranked in ((1.5, symbol), (1.2, lexical), (1.0, dense)):
            for rank, candidate in enumerate(ranked, start=1):
                candidates[candidate.evidence_id] = candidate
                scores[candidate.evidence_id] = scores.get(candidate.evidence_id, 0.0) + (
                    weight / (self._k + rank)
                )
        return sorted(
            (replace(candidate, score=scores[key]) for key, candidate in candidates.items()),
            key=lambda item: item.score,
            reverse=True,
        )
