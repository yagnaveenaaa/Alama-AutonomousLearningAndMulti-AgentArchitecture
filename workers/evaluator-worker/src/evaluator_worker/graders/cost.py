from __future__ import annotations

from evaluator_worker.domain.models import CostCase, MetricValue


def grade_cost(cases: list[CostCase]) -> tuple[list[MetricValue], dict[str, object]]:
    if not cases:
        return (
            [
                MetricValue(name="total_tokens", value=0.0, unit="tokens"),
                MetricValue(name="total_usd_micros", value=0.0, unit="usd_micros"),
                MetricValue(name="case_count", value=0.0, unit="count"),
            ],
            {"cases": []},
        )
    tokens = sum(c.tokens for c in cases)
    usd = sum(c.usd_micros for c in cases)
    return (
        [
            MetricValue(name="total_tokens", value=float(tokens), unit="tokens"),
            MetricValue(name="total_usd_micros", value=float(usd), unit="usd_micros"),
            MetricValue(
                name="avg_usd_micros",
                value=float(usd) / len(cases),
                unit="usd_micros",
            ),
            MetricValue(name="case_count", value=float(len(cases)), unit="count"),
        ],
        {
            "cases": [
                {"case_id": c.case_id, "tokens": c.tokens, "usd_micros": c.usd_micros}
                for c in cases
            ]
        },
    )
