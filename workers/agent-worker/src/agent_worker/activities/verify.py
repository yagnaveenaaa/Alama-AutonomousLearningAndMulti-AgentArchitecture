from __future__ import annotations

from typing import Any
from uuid import UUID

from agent_worker.agents.reviewer import ReviewerAgent
from agent_worker.agents.security import SecurityAgent
from agent_worker.agents.tester import TesterAgent
from agent_worker.protocols.artifacts import (
    AgentRole,
    ArtifactEnvelope,
    ArtifactType,
    DiffBundle,
    PlanStep,
    ToolResult,
    VerifierDecision,
    VerifyOutcome,
)
from agent_worker.protocols.bus import AgentMessageBus


class VerifyActivity:
    """Tester + Reviewer + Security checks (LLD §2.15 / §6.3).

    Roles run when required by step tags: ``test``, ``review``, ``security``.
    High-risk steps always include security even if the tag is omitted.
    """

    def __init__(
        self,
        tester: TesterAgent,
        reviewer: ReviewerAgent,
        security: SecurityAgent,
        bus: AgentMessageBus,
    ) -> None:
        self._tester = tester
        self._reviewer = reviewer
        self._security = security
        self._bus = bus

    async def run(
        self,
        *,
        task_id: UUID,
        step: PlanStep,
        diff: DiffBundle,
        tool_results: list[ToolResult],
        remaining_steps: int,
        objective: str = "",
        policy_constraints: dict[str, Any] | None = None,
    ) -> VerifyOutcome:
        tags = {t.lower() for t in step.tags}
        need_test = "test" in tags or not tags
        need_review = "review" in tags
        need_security = "security" in tags or step.risk.value == "high"

        test_report = None
        review_report = None
        security_report = None

        if need_test:
            test_report = await self._tester.verify(
                step=step, diff=diff, tool_results=tool_results
            )
            self._bus.publish(
                ArtifactEnvelope.create(
                    artifact_type=ArtifactType.TEST_REPORT,
                    task_id=task_id,
                    producer_role=AgentRole.TESTER,
                    payload={
                        "step_id": test_report.step_id,
                        "passed": test_report.passed,
                        "tests_run": test_report.tests_run,
                        "failures": list(test_report.failures),
                        "interpretation": test_report.interpretation,
                        "proposed_fix_step": test_report.proposed_fix_step,
                    },
                )
            )

        if need_review:
            review_report = await self._reviewer.review(
                step=step,
                objective=objective or step.goal,
                diff=diff,
                policy_constraints=policy_constraints,
            )
            self._bus.publish(
                ArtifactEnvelope.create(
                    artifact_type=ArtifactType.REVIEW_REPORT,
                    task_id=task_id,
                    producer_role=AgentRole.REVIEWER,
                    payload={
                        "step_id": review_report.step_id,
                        "approved": review_report.approved,
                        "findings": list(review_report.findings),
                        "policy_notes": list(review_report.policy_notes),
                        "summary": review_report.summary,
                    },
                )
            )

        if need_security:
            security_report = await self._security.review(
                step=step,
                diff=diff,
                policy_constraints=policy_constraints,
            )
            self._bus.publish(
                ArtifactEnvelope.create(
                    artifact_type=ArtifactType.SECURITY_REPORT,
                    task_id=task_id,
                    producer_role=AgentRole.SECURITY,
                    payload={
                        "step_id": security_report.step_id,
                        "passed": security_report.passed,
                        "findings": [
                            {
                                "severity": f.severity,
                                "kind": f.kind,
                                "detail": f.detail,
                                "path": f.path,
                            }
                            for f in security_report.findings
                        ],
                        "summary": security_report.summary,
                    },
                )
            )

        decision = self._gate(
            step=step,
            remaining_steps=remaining_steps,
            test_passed=test_report.passed if test_report else True,
            review_approved=review_report.approved if review_report else True,
            security_passed=security_report.passed if security_report else True,
        )
        return VerifyOutcome(
            decision=decision,
            test_report=test_report,
            review_report=review_report,
            security_report=security_report,
        )

    @staticmethod
    def _gate(
        *,
        step: PlanStep,
        remaining_steps: int,
        test_passed: bool,
        review_approved: bool,
        security_passed: bool,
    ) -> VerifierDecision:
        if step.approval_gates:
            return VerifierDecision.APPROVE_WAIT
        if not test_passed or not review_approved or not security_passed:
            return VerifierDecision.FAIL
        if remaining_steps <= 0:
            return VerifierDecision.COMPLETE
        return VerifierDecision.CONTINUE
