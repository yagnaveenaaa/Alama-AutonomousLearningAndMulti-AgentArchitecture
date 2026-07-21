from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from alama_common.errors import ValidationError
from alama_common.ids import new_uuid7


class EvalKind(StrEnum):
    RETRIEVAL_RECALL = "retrieval_recall"
    AGENT_SUCCESS = "agent_success"
    ATTRIBUTION = "attribution"
    SAFETY = "safety"
    COST = "cost"


class EvalJobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class GateDecision(StrEnum):
    PROMOTE = "promote"
    BLOCK = "block"


@dataclass(frozen=True, slots=True)
class EvalJob:
    """Queued eval work item (offline/online; never on hot path)."""

    id: UUID
    tenant_id: UUID
    kind: EvalKind
    suite_version: str
    candidate_ref: str
    baseline_scorecard_id: UUID | None
    status: EvalJobStatus
    created_at: datetime
    payload: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        tenant_id: UUID,
        kind: EvalKind,
        suite_version: str,
        candidate_ref: str,
        baseline_scorecard_id: UUID | None = None,
        payload: dict[str, Any] | None = None,
    ) -> EvalJob:
        if not suite_version.strip():
            raise ValidationError("suite_version is required")
        if not candidate_ref.strip():
            raise ValidationError("candidate_ref is required")
        return cls(
            id=new_uuid7(),
            tenant_id=tenant_id,
            kind=kind,
            suite_version=suite_version.strip(),
            candidate_ref=candidate_ref.strip(),
            baseline_scorecard_id=baseline_scorecard_id,
            status=EvalJobStatus.PENDING,
            created_at=datetime.now(UTC),
            payload=dict(payload or {}),
        )


@dataclass(frozen=True, slots=True)
class MetricValue:
    name: str
    value: float
    unit: str = "ratio"


@dataclass(frozen=True, slots=True)
class Scorecard:
    """Persisted eval result used by canary gates (LLD §2.16 / §15)."""

    id: UUID
    tenant_id: UUID
    job_id: UUID
    kind: EvalKind
    suite_version: str
    candidate_ref: str
    metrics: tuple[MetricValue, ...]
    details: dict[str, Any]
    created_at: datetime

    def metric(self, name: str) -> float | None:
        for item in self.metrics:
            if item.name == name:
                return item.value
        return None

    @classmethod
    def create(
        cls,
        *,
        tenant_id: UUID,
        job_id: UUID,
        kind: EvalKind,
        suite_version: str,
        candidate_ref: str,
        metrics: list[MetricValue],
        details: dict[str, Any] | None = None,
    ) -> Scorecard:
        return cls(
            id=new_uuid7(),
            tenant_id=tenant_id,
            job_id=job_id,
            kind=kind,
            suite_version=suite_version,
            candidate_ref=candidate_ref,
            metrics=tuple(metrics),
            details=dict(details or {}),
            created_at=datetime.now(UTC),
        )


@dataclass(frozen=True, slots=True)
class GateResult:
    decision: GateDecision
    reasons: tuple[str, ...]
    scorecard_id: UUID
    baseline_scorecard_id: UUID | None


@dataclass(frozen=True, slots=True)
class RetrievalGoldenCase:
    query_id: str
    query: str
    expected_evidence_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AgentGoldenCase:
    case_id: str
    objective: str
    expected_success: bool
    observed_success: bool


@dataclass(frozen=True, slots=True)
class AttributionCase:
    case_id: str
    claim_count: int
    unsupported_count: int


@dataclass(frozen=True, slots=True)
class SafetyCase:
    case_id: str
    prompt: str
    should_block: bool
    blocked: bool


@dataclass(frozen=True, slots=True)
class CostCase:
    case_id: str
    tokens: int
    usd_micros: int
