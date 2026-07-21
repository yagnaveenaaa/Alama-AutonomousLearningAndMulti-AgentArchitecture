from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from agent_worker.protocols.artifacts import (
    DiffBundle,
    Plan,
    PlanStep,
    ReviewReport,
    SecurityReport,
    TestReport,
    ToolCallIntent,
    ToolResult,
)


class ModelGatewayPort(Protocol):
    """Only path to LLM providers — used via prompt templates (LLD §2.9 / §6.8)."""

    async def complete_json(
        self,
        *,
        template_name: str,
        inputs: dict[str, Any],
        schema_name: str,
    ) -> dict[str, Any]: ...


class ToolGatewayPort(Protocol):
    """Only path for side effects (LLD §2.10 / §6.5)."""

    async def invoke(
        self,
        *,
        task_id: UUID,
        intent: ToolCallIntent,
    ) -> ToolResult: ...


class RetrievalPort(Protocol):
    async def retrieve(
        self,
        *,
        tenant_id: UUID,
        repository_id: UUID,
        commit_sha: str,
        query: str,
    ) -> dict[str, Any]: ...


class TaskProjectionPort(Protocol):
    """Notify task-service of workflow projection updates."""

    async def project_event(
        self,
        *,
        task_id: UUID,
        event_type: str,
        payload: dict[str, Any],
    ) -> None: ...


class PlannerPort(Protocol):
    async def draft_plan(
        self,
        *,
        objective: str,
        retrieval_pack: dict[str, Any],
        policy_constraints: dict[str, Any],
    ) -> Plan: ...


class CoderPort(Protocol):
    async def execute_step(
        self,
        *,
        step: PlanStep,
        retrieval_pack: dict[str, Any],
        prior_failures: list[str],
    ) -> tuple[DiffBundle, list[ToolCallIntent]]: ...


class TesterPort(Protocol):
    async def verify(
        self,
        *,
        step: PlanStep,
        diff: DiffBundle,
        tool_results: list[ToolResult],
    ) -> TestReport: ...


class ReviewerPort(Protocol):
    async def review(
        self,
        *,
        step: PlanStep,
        objective: str,
        diff: DiffBundle,
        policy_constraints: dict[str, Any] | None = None,
    ) -> ReviewReport: ...


class SecurityPort(Protocol):
    async def review(
        self,
        *,
        step: PlanStep,
        diff: DiffBundle,
        policy_constraints: dict[str, Any] | None = None,
    ) -> SecurityReport: ...
