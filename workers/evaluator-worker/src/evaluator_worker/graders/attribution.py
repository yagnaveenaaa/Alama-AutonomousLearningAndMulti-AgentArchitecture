from __future__ import annotations

from evaluator_worker.domain.models import AttributionCase, MetricValue


def grade_attribution(
    cases: list[AttributionCase],
) -> tuple[list[MetricValue], dict[str, object]]:
    if not cases:
        return (
            [
                MetricValue(name="unsupported_claim_rate", value=0.0),
                MetricValue(name="case_count", value=0.0, unit="count"),
            ],
            {"cases": []},
        )
    claims = sum(c.claim_count for c in cases)
    unsupported = sum(c.unsupported_count for c in cases)
    rate = (unsupported / claims) if claims else 0.0
    return (
        [
            MetricValue(name="unsupported_claim_rate", value=rate),
            MetricValue(name="claim_count", value=float(claims), unit="count"),
            MetricValue(name="case_count", value=float(len(cases)), unit="count"),
        ],
        {
            "cases": [
                {
                    "case_id": c.case_id,
                    "claim_count": c.claim_count,
                    "unsupported_count": c.unsupported_count,
                }
                for c in cases
            ]
        },
    )
