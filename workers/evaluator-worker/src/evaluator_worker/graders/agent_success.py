from __future__ import annotations

from evaluator_worker.domain.models import AgentGoldenCase, MetricValue


def grade_agent_success(
    cases: list[AgentGoldenCase],
) -> tuple[list[MetricValue], dict[str, object]]:
    if not cases:
        return (
            [
                MetricValue(name="success_rate", value=0.0),
                MetricValue(name="case_count", value=0.0, unit="count"),
            ],
            {"cases": []},
        )
    matched = sum(1 for c in cases if c.observed_success == c.expected_success)
    rate = matched / len(cases)
    return (
        [
            MetricValue(name="success_rate", value=rate),
            MetricValue(name="case_count", value=float(len(cases)), unit="count"),
        ],
        {
            "matched": matched,
            "cases": [
                {
                    "case_id": c.case_id,
                    "expected": c.expected_success,
                    "observed": c.observed_success,
                }
                for c in cases
            ],
        },
    )
