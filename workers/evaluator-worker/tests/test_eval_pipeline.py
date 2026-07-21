from __future__ import annotations

from uuid import uuid4

import pytest

from evaluator_worker.config import EvaluatorWorkerSettings
from evaluator_worker.container import build_container
from evaluator_worker.domain.models import (
    AttributionCase,
    EvalJob,
    EvalKind,
    GateDecision,
    RetrievalGoldenCase,
)
from evaluator_worker.main import process_one


@pytest.mark.asyncio
async def test_retrieval_recall_promotes() -> None:
    container = build_container(
        EvaluatorWorkerSettings(min_retrieval_recall_at_k=0.5, retrieval_k=5)
    )
    suite = "v1"
    container.goldens.seed_retrieval(
        suite,
        [
            RetrievalGoldenCase(
                query_id="q1",
                query="Where is Greeter.hello?",
                expected_evidence_ids=("src/demo.py:Greeter.hello",),
            ),
            RetrievalGoldenCase(
                query_id="q2",
                query="add ints",
                expected_evidence_ids=("src/demo.py:add",),
            ),
        ],
    )
    container.retrieval.put_results(
        "Where is Greeter.hello?",
        ["src/demo.py:Greeter.hello", "other"],
    )
    container.retrieval.put_results(
        "add ints",
        ["noise", "src/demo.py:add"],
    )

    job = EvalJob.create(
        tenant_id=uuid4(),
        kind=EvalKind.RETRIEVAL_RECALL,
        suite_version=suite,
        candidate_ref="retrieval-candidate-1",
    )
    await container.queue.enqueue(job)
    assert await process_one(container) is True

    scorecard = next(iter(container.store.scorecards.values()))
    assert scorecard.metric("recall_at_k") == 1.0
    assert scorecard.metric("mrr") == pytest.approx(0.75)
    gate = container.store.gates[-1]
    assert gate.decision == GateDecision.PROMOTE


@pytest.mark.asyncio
async def test_attribution_blocks_on_threshold() -> None:
    container = build_container(
        EvaluatorWorkerSettings(max_unsupported_claim_rate=0.1)
    )
    suite = "attr-v1"
    container.goldens.seed_attribution(
        suite,
        [
            AttributionCase(case_id="c1", claim_count=10, unsupported_count=3),
        ],
    )
    job = EvalJob.create(
        tenant_id=uuid4(),
        kind=EvalKind.ATTRIBUTION,
        suite_version=suite,
        candidate_ref="agent-prompt-v2",
    )
    await container.queue.enqueue(job)
    assert await process_one(container) is True
    gate = container.store.gates[-1]
    assert gate.decision == GateDecision.BLOCK
    assert any("unsupported_claim_rate" in r for r in gate.reasons)


@pytest.mark.asyncio
async def test_regression_blocks_promote() -> None:
    container = build_container(
        EvaluatorWorkerSettings(
            min_retrieval_recall_at_k=0.0,
            max_regression=0.05,
            retrieval_k=5,
        )
    )
    suite = "reg-v1"
    container.goldens.seed_retrieval(
        suite,
        [
            RetrievalGoldenCase(
                query_id="q1",
                query="q",
                expected_evidence_ids=("e1",),
            )
        ],
    )
    container.retrieval.put_results("q", ["e1"])

    baseline_job = EvalJob.create(
        tenant_id=uuid4(),
        kind=EvalKind.RETRIEVAL_RECALL,
        suite_version=suite,
        candidate_ref="baseline",
    )
    await container.queue.enqueue(baseline_job)
    await process_one(container)
    baseline = next(iter(container.store.scorecards.values()))

    # Candidate misses the evidence → recall 0 → regression
    container.retrieval.put_results("q", ["wrong"])
    candidate_job = EvalJob.create(
        tenant_id=baseline_job.tenant_id,
        kind=EvalKind.RETRIEVAL_RECALL,
        suite_version=suite,
        candidate_ref="worse",
        baseline_scorecard_id=baseline.id,
    )
    await container.queue.enqueue(candidate_job)
    await process_one(container)
    gate = container.store.gates[-1]
    assert gate.decision == GateDecision.BLOCK
    assert any("regressed" in r for r in gate.reasons)
