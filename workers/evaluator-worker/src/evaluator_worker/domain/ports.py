from __future__ import annotations

from typing import Protocol
from uuid import UUID

from evaluator_worker.domain.models import (
    AgentGoldenCase,
    AttributionCase,
    CostCase,
    EvalJob,
    RetrievalGoldenCase,
    SafetyCase,
    Scorecard,
)


class EvalJobQueue(Protocol):
    async def enqueue(self, job: EvalJob) -> None: ...

    async def dequeue(self) -> EvalJob | None: ...


class ScorecardRepository(Protocol):
    async def save(self, scorecard: Scorecard) -> None: ...

    async def get(self, scorecard_id: UUID) -> Scorecard | None: ...

    async def latest_for_kind(
        self, tenant_id: UUID, kind: str, suite_version: str
    ) -> Scorecard | None: ...


class RetrievalPort(Protocol):
    """Narrow retrieval surface for recall@k grading."""

    async def retrieve(self, *, query: str, k: int) -> list[str]: ...


class GoldenSetStore(Protocol):
    async def retrieval_cases(self, suite_version: str) -> list[RetrievalGoldenCase]: ...

    async def agent_cases(self, suite_version: str) -> list[AgentGoldenCase]: ...

    async def attribution_cases(self, suite_version: str) -> list[AttributionCase]: ...

    async def safety_cases(self, suite_version: str) -> list[SafetyCase]: ...

    async def cost_cases(self, suite_version: str) -> list[CostCase]: ...
