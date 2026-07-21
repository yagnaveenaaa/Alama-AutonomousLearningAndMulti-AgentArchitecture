from __future__ import annotations

from evaluator_worker.domain.models import MetricValue, RetrievalGoldenCase
from evaluator_worker.domain.ports import RetrievalPort


async def grade_retrieval_recall(
    cases: list[RetrievalGoldenCase],
    retrieval: RetrievalPort,
    *,
    k: int,
) -> tuple[list[MetricValue], dict[str, object]]:
    """Deterministic recall@k / MRR over golden retrieval cases."""
    if not cases:
        return (
            [
                MetricValue(name="recall_at_k", value=0.0),
                MetricValue(name="mrr", value=0.0),
                MetricValue(name="case_count", value=0.0, unit="count"),
            ],
            {"cases": []},
        )

    recalls: list[float] = []
    reciprocal_ranks: list[float] = []
    per_case: list[dict[str, object]] = []
    for case in cases:
        hits = await retrieval.retrieve(query=case.query, k=k)
        expected = set(case.expected_evidence_ids)
        found = [h for h in hits if h in expected]
        recall = len(found) / len(expected) if expected else 0.0
        recalls.append(recall)
        rr = 0.0
        for idx, hit in enumerate(hits, start=1):
            if hit in expected:
                rr = 1.0 / idx
                break
        reciprocal_ranks.append(rr)
        per_case.append(
            {
                "query_id": case.query_id,
                "recall": recall,
                "rr": rr,
                "hits": hits,
            }
        )

    avg_recall = sum(recalls) / len(recalls)
    mrr = sum(reciprocal_ranks) / len(reciprocal_ranks)
    return (
        [
            MetricValue(name="recall_at_k", value=avg_recall),
            MetricValue(name="mrr", value=mrr),
            MetricValue(name="case_count", value=float(len(cases)), unit="count"),
        ],
        {"k": k, "cases": per_case},
    )
