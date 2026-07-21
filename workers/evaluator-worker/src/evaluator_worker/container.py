from __future__ import annotations

from dataclasses import dataclass

from evaluator_worker.adapters.persistence.memory import (
    InMemoryEvalJobQueue,
    InMemoryEvalStore,
    InMemoryGoldenSetStore,
    InMemoryRetrievalPort,
    InMemoryScorecardRepository,
)
from evaluator_worker.application.canary_gate import CanaryGate
from evaluator_worker.application.eval_runner import EvalRunner
from evaluator_worker.config import EvaluatorWorkerSettings


@dataclass
class EvaluatorWorkerContainer:
    settings: EvaluatorWorkerSettings
    store: InMemoryEvalStore
    queue: InMemoryEvalJobQueue
    scorecards: InMemoryScorecardRepository
    goldens: InMemoryGoldenSetStore
    retrieval: InMemoryRetrievalPort
    runner: EvalRunner
    gate: CanaryGate


def build_container(
    settings: EvaluatorWorkerSettings | None = None,
) -> EvaluatorWorkerContainer:
    settings = settings or EvaluatorWorkerSettings()
    store = InMemoryEvalStore()
    queue = InMemoryEvalJobQueue(store)
    scorecards = InMemoryScorecardRepository(store)
    goldens = InMemoryGoldenSetStore(store)
    retrieval = InMemoryRetrievalPort(store)
    gate = CanaryGate(settings)
    runner = EvalRunner(scorecards, goldens, retrieval, gate, settings)
    return EvaluatorWorkerContainer(
        settings=settings,
        store=store,
        queue=queue,
        scorecards=scorecards,
        goldens=goldens,
        retrieval=retrieval,
        runner=runner,
        gate=gate,
    )
