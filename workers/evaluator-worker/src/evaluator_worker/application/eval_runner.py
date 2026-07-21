from __future__ import annotations

from evaluator_worker.application.canary_gate import CanaryGate
from evaluator_worker.config import EvaluatorWorkerSettings
from evaluator_worker.domain.models import (
    EvalJob,
    EvalKind,
    GateResult,
    MetricValue,
    Scorecard,
)
from evaluator_worker.domain.ports import (
    GoldenSetStore,
    RetrievalPort,
    ScorecardRepository,
)
from evaluator_worker.graders.agent_success import grade_agent_success
from evaluator_worker.graders.attribution import grade_attribution
from evaluator_worker.graders.cost import grade_cost
from evaluator_worker.graders.retrieval_recall import grade_retrieval_recall
from evaluator_worker.graders.safety import grade_safety


class EvalRunner:
    """Run one eval job → graders → scorecard → canary gate (LLD §2.16)."""

    def __init__(
        self,
        scorecards: ScorecardRepository,
        goldens: GoldenSetStore,
        retrieval: RetrievalPort,
        gate: CanaryGate,
        settings: EvaluatorWorkerSettings,
    ) -> None:
        self._scorecards = scorecards
        self._goldens = goldens
        self._retrieval = retrieval
        self._gate = gate
        self._settings = settings
        self.last_gate: GateResult | None = None

    async def run(self, job: EvalJob) -> tuple[Scorecard, GateResult]:
        metrics, details = await self._grade(job)
        scorecard = Scorecard.create(
            tenant_id=job.tenant_id,
            job_id=job.id,
            kind=job.kind,
            suite_version=job.suite_version,
            candidate_ref=job.candidate_ref,
            metrics=metrics,
            details=details,
        )
        await self._scorecards.save(scorecard)

        baseline = None
        if job.baseline_scorecard_id is not None:
            baseline = await self._scorecards.get(job.baseline_scorecard_id)
        gate = self._gate.decide(scorecard, baseline=baseline)
        self.last_gate = gate
        return scorecard, gate

    async def _grade(
        self, job: EvalJob
    ) -> tuple[list[MetricValue], dict[str, object]]:
        if job.kind == EvalKind.RETRIEVAL_RECALL:
            return await grade_retrieval_recall(
                await self._goldens.retrieval_cases(job.suite_version),
                self._retrieval,
                k=self._settings.retrieval_k,
            )
        if job.kind == EvalKind.AGENT_SUCCESS:
            return grade_agent_success(
                await self._goldens.agent_cases(job.suite_version)
            )
        if job.kind == EvalKind.ATTRIBUTION:
            return grade_attribution(
                await self._goldens.attribution_cases(job.suite_version)
            )
        if job.kind == EvalKind.SAFETY:
            return grade_safety(await self._goldens.safety_cases(job.suite_version))
        if job.kind == EvalKind.COST:
            return grade_cost(await self._goldens.cost_cases(job.suite_version))
        raise ValueError(f"Unsupported eval kind: {job.kind}")
