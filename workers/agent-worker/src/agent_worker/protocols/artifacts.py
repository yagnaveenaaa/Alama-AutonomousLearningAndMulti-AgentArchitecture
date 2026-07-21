"""Versioned agent artifact schemas (LLD §6.2 / Appendix A)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from alama_common.errors import ValidationError
from alama_common.ids import new_uuid7


class ArtifactType(StrEnum):
    PLAN = "Plan"
    STEP_RESULT = "StepResult"
    DIFF_BUNDLE = "DiffBundle"
    TEST_REPORT = "TestReport"
    REVIEW_REPORT = "ReviewReport"
    SECURITY_REPORT = "SecurityReport"
    REFLECTION = "Reflection"
    MEMORY_CANDIDATE = "MemoryCandidate"
    USER_SUMMARY = "UserSummary"
    RETRIEVAL_PACK = "RetrievalPack"
    TOOL_CALL_INTENT = "ToolCallIntent"
    TOOL_RESULT = "ToolResult"
    TOOL_RECEIPT = "ToolReceipt"


class AgentRole(StrEnum):
    PLANNER = "planner"
    CODER = "coder"
    TESTER = "tester"
    REVIEWER = "reviewer"
    SECURITY = "security"
    DOCUMENTATION = "documentation"
    MEMORY_WRITER = "memory_writer"
    RECOVERY = "recovery"
    SUMMARIZER = "summarizer"
    CONTEXT_BUILDER = "context_builder"
    SYSTEM = "system"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class VerifierDecision(StrEnum):
    CONTINUE = "continue"
    APPROVE_WAIT = "approve_wait"
    FAIL = "fail"
    COMPLETE = "complete"


@dataclass(frozen=True, slots=True)
class EvidenceRef:
    evidence_id: UUID
    path: str
    start: int
    end: int
    commit: str


@dataclass(frozen=True, slots=True)
class ArtifactEnvelope:
    """Typed handoff envelope — agents do not free-chat (LLD §6.2)."""

    artifact_id: UUID
    artifact_type: ArtifactType
    task_id: UUID
    producer_role: AgentRole
    schema_version: str
    created_at: datetime
    payload: dict[str, Any]
    payload_ref: str | None = None
    citations: tuple[EvidenceRef, ...] = ()
    policy_version: str = "policy.v1"

    @classmethod
    def create(
        cls,
        *,
        artifact_type: ArtifactType,
        task_id: UUID,
        producer_role: AgentRole,
        payload: dict[str, Any],
        schema_version: str = "1.0.0",
        citations: tuple[EvidenceRef, ...] = (),
        policy_version: str = "policy.v1",
        payload_ref: str | None = None,
    ) -> ArtifactEnvelope:
        return cls(
            artifact_id=new_uuid7(),
            artifact_type=artifact_type,
            task_id=task_id,
            producer_role=producer_role,
            schema_version=schema_version,
            created_at=datetime.now(UTC),
            payload=payload,
            payload_ref=payload_ref,
            citations=citations,
            policy_version=policy_version,
        )


@dataclass(frozen=True, slots=True)
class PlanStep:
    step_id: str
    goal: str
    files_likely: tuple[str, ...]
    tools_needed: tuple[str, ...]
    risk: RiskLevel
    verification: str
    approval_gates: tuple[str, ...]
    stop_conditions: tuple[str, ...]
    depends_on: tuple[str, ...] = ()
    tags: tuple[str, ...] = ("test",)

    def __post_init__(self) -> None:
        if not self.step_id.strip() or not self.goal.strip():
            raise ValidationError("PlanStep requires step_id and goal")


@dataclass(frozen=True, slots=True)
class Plan:
    objective: str
    steps: tuple[PlanStep, ...]
    success_criteria: tuple[str, ...]
    risks: tuple[str, ...]
    stop_conditions: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.objective.strip():
            raise ValidationError("Plan objective is required")
        if not self.steps:
            raise ValidationError("Plan must include at least one step")

    def to_payload(self) -> dict[str, Any]:
        return {
            "objective": self.objective,
            "success_criteria": list(self.success_criteria),
            "risks": list(self.risks),
            "stop_conditions": list(self.stop_conditions),
            "steps": [
                {
                    "step_id": s.step_id,
                    "goal": s.goal,
                    "files_likely": list(s.files_likely),
                    "tools_needed": list(s.tools_needed),
                    "risk": s.risk.value,
                    "verification": s.verification,
                    "approval_gates": list(s.approval_gates),
                    "stop_conditions": list(s.stop_conditions),
                    "depends_on": list(s.depends_on),
                    "tags": list(s.tags),
                }
                for s in self.steps
            ],
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> Plan:
        steps = tuple(
            PlanStep(
                step_id=str(raw["step_id"]),
                goal=str(raw["goal"]),
                files_likely=tuple(raw.get("files_likely", [])),
                tools_needed=tuple(raw.get("tools_needed", [])),
                risk=RiskLevel(str(raw.get("risk", "low"))),
                verification=str(raw.get("verification", "run_tests")),
                approval_gates=tuple(raw.get("approval_gates", [])),
                stop_conditions=tuple(raw.get("stop_conditions", [])),
                depends_on=tuple(raw.get("depends_on", [])),
                tags=tuple(raw.get("tags", ("test",))),
            )
            for raw in payload.get("steps", [])
        )
        return cls(
            objective=str(payload["objective"]),
            steps=steps,
            success_criteria=tuple(payload.get("success_criteria", [])),
            risks=tuple(payload.get("risks", [])),
            stop_conditions=tuple(payload.get("stop_conditions", [])),
        )


@dataclass(frozen=True, slots=True)
class ToolCallIntent:
    name: str
    args: dict[str, Any]
    reason: str

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValidationError("ToolCallIntent.name is required")


@dataclass(frozen=True, slots=True)
class ToolResult:
    name: str
    ok: bool
    output: str
    receipt_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class DiffBundle:
    step_id: str
    summary: str
    patches: tuple[dict[str, str], ...]
    tool_intents: tuple[ToolCallIntent, ...]


@dataclass(frozen=True, slots=True)
class StepResult:
    step_id: str
    status: str
    summary: str
    tool_results: tuple[ToolResult, ...] = ()


@dataclass(frozen=True, slots=True)
class TestReport:
    step_id: str
    passed: bool
    tests_run: int
    failures: tuple[str, ...]
    interpretation: str
    proposed_fix_step: str | None = None


@dataclass(frozen=True, slots=True)
class ReviewReport:
    """Independent review of diff vs objective/policy (LLD §6.1)."""

    step_id: str
    approved: bool
    findings: tuple[str, ...]
    policy_notes: tuple[str, ...]
    summary: str


@dataclass(frozen=True, slots=True)
class SecurityFinding:
    severity: str
    kind: str
    detail: str
    path: str | None = None


@dataclass(frozen=True, slots=True)
class SecurityReport:
    """Secret/vuln/authz review of changes (LLD §6.1 / §13)."""

    step_id: str
    passed: bool
    findings: tuple[SecurityFinding, ...]
    summary: str

    @property
    def blocking_findings(self) -> tuple[SecurityFinding, ...]:
        return tuple(
            f for f in self.findings if f.severity in {"high", "critical", "secret"}
        )


@dataclass(frozen=True, slots=True)
class VerifyOutcome:
    """Aggregated Tester + Reviewer + Security result for the verifier gate."""

    decision: VerifierDecision
    test_report: TestReport | None = None
    review_report: ReviewReport | None = None
    security_report: SecurityReport | None = None

    @property
    def failure_messages(self) -> tuple[str, ...]:
        messages: list[str] = []
        if self.test_report is not None and not self.test_report.passed:
            messages.extend(self.test_report.failures or (self.test_report.interpretation,))
        if self.review_report is not None and not self.review_report.approved:
            messages.extend(self.review_report.findings or (self.review_report.summary,))
        if self.security_report is not None and not self.security_report.passed:
            if self.security_report.findings:
                messages.extend(
                    f"{f.severity}:{f.kind}:{f.detail}"
                    for f in self.security_report.findings
                )
            else:
                messages.append(self.security_report.summary)
        return tuple(messages)


@dataclass
class WorkingMemory:
    """Compact workflow working memory (LLD §8)."""

    task_id: UUID
    objective: str
    repository_id: UUID
    commit_sha: str
    plan: Plan | None = None
    retrieval_summary: str = ""
    artifacts: list[ArtifactEnvelope] = field(default_factory=list)
    completed_steps: list[str] = field(default_factory=list)
    reflections: int = 0
    replans: int = 0

    def latest(self, artifact_type: ArtifactType) -> ArtifactEnvelope | None:
        for item in reversed(self.artifacts):
            if item.artifact_type == artifact_type:
                return item
        return None
