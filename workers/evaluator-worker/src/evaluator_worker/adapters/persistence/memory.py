from __future__ import annotations

from uuid import UUID

from evaluator_worker.domain.models import (
    AgentGoldenCase,
    AttributionCase,
    CostCase,
    EvalJob,
    GateResult,
    RetrievalGoldenCase,
    SafetyCase,
    Scorecard,
)


class InMemoryEvalStore:
    def __init__(self) -> None:
        self.jobs: list[EvalJob] = []
        self.scorecards: dict[UUID, Scorecard] = {}
        self.retrieval_index: dict[str, list[str]] = {}
        self.retrieval_cases: dict[str, list[RetrievalGoldenCase]] = {}
        self.agent_cases: dict[str, list[AgentGoldenCase]] = {}
        self.attribution_cases: dict[str, list[AttributionCase]] = {}
        self.safety_cases: dict[str, list[SafetyCase]] = {}
        self.cost_cases: dict[str, list[CostCase]] = {}
        self.gates: list[GateResult] = []


class InMemoryEvalJobQueue:
    def __init__(self, store: InMemoryEvalStore) -> None:
        self._store = store

    async def enqueue(self, job: EvalJob) -> None:
        self._store.jobs.append(job)

    async def dequeue(self) -> EvalJob | None:
        if not self._store.jobs:
            return None
        return self._store.jobs.pop(0)


class InMemoryScorecardRepository:
    def __init__(self, store: InMemoryEvalStore) -> None:
        self._store = store

    async def save(self, scorecard: Scorecard) -> None:
        self._store.scorecards[scorecard.id] = scorecard

    async def get(self, scorecard_id: UUID) -> Scorecard | None:
        return self._store.scorecards.get(scorecard_id)

    async def latest_for_kind(
        self, tenant_id: UUID, kind: str, suite_version: str
    ) -> Scorecard | None:
        items = [
            s
            for s in self._store.scorecards.values()
            if s.tenant_id == tenant_id
            and s.kind.value == kind
            and s.suite_version == suite_version
        ]
        if not items:
            return None
        items.sort(key=lambda s: s.created_at, reverse=True)
        return items[0]


class InMemoryRetrievalPort:
    def __init__(self, store: InMemoryEvalStore) -> None:
        self._store = store

    def put_results(self, query: str, evidence_ids: list[str]) -> None:
        self._store.retrieval_index[query] = list(evidence_ids)

    async def retrieve(self, *, query: str, k: int) -> list[str]:
        return list(self._store.retrieval_index.get(query, []))[:k]


class InMemoryGoldenSetStore:
    def __init__(self, store: InMemoryEvalStore) -> None:
        self._store = store

    def seed_retrieval(self, suite_version: str, cases: list[RetrievalGoldenCase]) -> None:
        self._store.retrieval_cases[suite_version] = list(cases)

    def seed_agent(self, suite_version: str, cases: list[AgentGoldenCase]) -> None:
        self._store.agent_cases[suite_version] = list(cases)

    def seed_attribution(self, suite_version: str, cases: list[AttributionCase]) -> None:
        self._store.attribution_cases[suite_version] = list(cases)

    def seed_safety(self, suite_version: str, cases: list[SafetyCase]) -> None:
        self._store.safety_cases[suite_version] = list(cases)

    def seed_cost(self, suite_version: str, cases: list[CostCase]) -> None:
        self._store.cost_cases[suite_version] = list(cases)

    async def retrieval_cases(self, suite_version: str) -> list[RetrievalGoldenCase]:
        return list(self._store.retrieval_cases.get(suite_version, []))

    async def agent_cases(self, suite_version: str) -> list[AgentGoldenCase]:
        return list(self._store.agent_cases.get(suite_version, []))

    async def attribution_cases(self, suite_version: str) -> list[AttributionCase]:
        return list(self._store.attribution_cases.get(suite_version, []))

    async def safety_cases(self, suite_version: str) -> list[SafetyCase]:
        return list(self._store.safety_cases.get(suite_version, []))

    async def cost_cases(self, suite_version: str) -> list[CostCase]:
        return list(self._store.cost_cases.get(suite_version, []))
