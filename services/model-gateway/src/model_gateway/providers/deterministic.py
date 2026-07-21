from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any

from alama_common.ids import new_uuid7

from model_gateway.domain.models import (
    CompletionResult,
    EmbeddingResult,
    ModelProfile,
    ModelRequest,
    RerankResult,
)


class DeterministicProviderAdapter:
    """Local OpenAI-class stand-in for tests/dev (no vendor SDK)."""

    name = "deterministic"

    def __init__(self, *, embedding_dim: int = 64) -> None:
        self._embedding_dim = embedding_dim

    async def complete(
        self, request: ModelRequest, profile: ModelProfile
    ) -> CompletionResult:
        user_text = " ".join(m.content for m in request.messages if m.role == "user")
        system_text = " ".join(m.content for m in request.messages if m.role == "system")
        content: str
        parsed: dict[str, Any] | None = None
        if request.json_schema_name == "Plan" or "planner" in (request.template_name or ""):
            objective = str(request.template_inputs.get("objective") or user_text or "task")
            parsed = {
                "objective": objective,
                "success_criteria": ["tests pass"],
                "risks": ["regression"],
                "stop_conditions": ["budget exhausted"],
                "steps": [
                    {
                        "step_id": "step-1",
                        "goal": f"Implement: {objective}",
                        "files_likely": ["src/main.py"],
                        "tools_needed": ["get_file", "apply_patch", "run_tests"],
                        "risk": "medium",
                        "verification": "run unit tests",
                        "approval_gates": [],
                        "stop_conditions": [],
                        "depends_on": [],
                        "tags": ["test"],
                    }
                ],
            }
            content = json.dumps(parsed)
        else:
            content = f"[{profile.name}] {user_text or system_text[:200]}"
            if request.json_schema_name:
                parsed = {"content": content}
                content = json.dumps(parsed)
        input_tokens = max(1, sum(len(m.content) for m in request.messages) // 4)
        output_tokens = max(1, len(content) // 4)
        return CompletionResult(
            request_id=new_uuid7(),
            model=profile.name,
            provider=self.name,
            content=content,
            parsed_json=parsed,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            fallback_used=False,
        )

    async def embed(
        self, request: ModelRequest, profile: ModelProfile
    ) -> EmbeddingResult:
        vectors = tuple(self._embed_one(text) for text in request.texts)
        tokens = max(1, sum(len(t) for t in request.texts) // 4)
        return EmbeddingResult(
            request_id=new_uuid7(),
            model=profile.name,
            provider=self.name,
            vectors=vectors,
            input_tokens=tokens,
            dimension=self._embedding_dim,
        )

    async def rerank(
        self, request: ModelRequest, profile: ModelProfile
    ) -> RerankResult:
        query_terms = set(re.findall(r"[a-z0-9_]+", (request.query or "").lower()))
        scored: list[tuple[int, float]] = []
        for idx, doc in enumerate(request.documents):
            doc_terms = set(re.findall(r"[a-z0-9_]+", doc.lower()))
            union = query_terms | doc_terms
            score = len(query_terms & doc_terms) / len(union) if union else 0.0
            scored.append((idx, score))
        scored.sort(key=lambda item: item[1], reverse=True)
        tokens = max(1, (len(request.query or "") + sum(len(d) for d in request.documents)) // 4)
        return RerankResult(
            request_id=new_uuid7(),
            model=profile.name,
            provider=self.name,
            ranked_indices=tuple(i for i, _ in scored),
            scores=tuple(s for _, s in scored),
            input_tokens=tokens,
        )

    def _embed_one(self, text: str) -> tuple[float, ...]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values = [
            ((digest[i % len(digest)] / 255.0) * 2.0 - 1.0)
            for i in range(self._embedding_dim)
        ]
        norm = math.sqrt(sum(v * v for v in values)) or 1.0
        return tuple(v / norm for v in values)


class TransientFailThenOkAdapter:
    """Provider that fails once then succeeds — exercises fallback routing."""

    name = "flaky"

    def __init__(self, inner: DeterministicProviderAdapter) -> None:
        self._inner = inner
        self.failures_remaining = 1

    async def complete(
        self, request: ModelRequest, profile: ModelProfile
    ) -> CompletionResult:
        from alama_common.errors import DependencyTransientError

        if self.failures_remaining > 0:
            self.failures_remaining -= 1
            raise DependencyTransientError("provider timeout")
        return await self._inner.complete(request, profile)

    async def embed(
        self, request: ModelRequest, profile: ModelProfile
    ) -> EmbeddingResult:
        return await self._inner.embed(request, profile)

    async def rerank(
        self, request: ModelRequest, profile: ModelProfile
    ) -> RerankResult:
        return await self._inner.rerank(request, profile)
