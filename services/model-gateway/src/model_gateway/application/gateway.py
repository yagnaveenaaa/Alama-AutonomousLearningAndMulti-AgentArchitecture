from __future__ import annotations

from alama_common.errors import DependencyTransientError

from model_gateway.domain.models import (
    ChatMessage,
    CompletionResult,
    EmbeddingResult,
    ModelRequest,
    RerankResult,
    UsageRecord,
)
from model_gateway.domain.ports import (
    PromptTemplateRegistry,
    ProviderAdapter,
    QuotaPort,
    UsageEmitter,
)
from model_gateway.policy.egress import EgressPolicy
from model_gateway.policy.redaction import RedactionFilter
from model_gateway.router.model_router import ModelRouter, ProviderRegistry


class ModelGatewayService:
    """Facade: redact → route → provider (with fallback) → account (LLD §2.9)."""

    def __init__(
        self,
        router: ModelRouter,
        providers: ProviderRegistry,
        templates: PromptTemplateRegistry,
        usage: UsageEmitter,
        quotas: QuotaPort,
        redaction: RedactionFilter,
        egress: EgressPolicy,
    ) -> None:
        self._router = router
        self._providers = providers
        self._templates = templates
        self._usage = usage
        self._quotas = quotas
        self._redaction = redaction
        self._egress = egress

    async def complete(self, request: ModelRequest) -> CompletionResult:
        self._egress.assert_allowed(request)
        prepared = await self._prepare_complete(request)
        primary, fallbacks = self._router.route(prepared)
        try:
            result = await self._provider(primary.provider).complete(prepared, primary)
        except DependencyTransientError:
            if not fallbacks:
                raise
            fb = fallbacks[0]
            result = await self._provider(fb.provider).complete(prepared, fb)
            result = CompletionResult(
                request_id=result.request_id,
                model=result.model,
                provider=result.provider,
                content=result.content,
                parsed_json=result.parsed_json,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                fallback_used=True,
            )
        await self._account(
            request,
            model=result.model,
            provider=result.provider,
            tokens=result.input_tokens + result.output_tokens,
        )
        return result

    async def embed(self, request: ModelRequest) -> EmbeddingResult:
        self._egress.assert_allowed(request)
        redacted = ModelRequest(
            tenant_id=request.tenant_id,
            task_id=request.task_id,
            purpose=request.purpose,
            capability=request.capability,
            preferred_tier=request.preferred_tier,
            residency=request.residency,
            texts=tuple(self._redaction.redact(t) for t in request.texts),
            max_tokens=request.max_tokens,
        )
        primary, fallbacks = self._router.route(redacted)
        try:
            result = await self._provider(primary.provider).embed(redacted, primary)
        except DependencyTransientError:
            if not fallbacks:
                raise
            result = await self._provider(fallbacks[0].provider).embed(redacted, fallbacks[0])
        await self._account(
            request,
            model=result.model,
            provider=result.provider,
            tokens=result.input_tokens,
        )
        return result

    async def rerank(self, request: ModelRequest) -> RerankResult:
        self._egress.assert_allowed(request)
        redacted = ModelRequest(
            tenant_id=request.tenant_id,
            task_id=request.task_id,
            purpose=request.purpose,
            capability=request.capability,
            preferred_tier=request.preferred_tier,
            residency=request.residency,
            query=self._redaction.redact(request.query or ""),
            documents=tuple(self._redaction.redact(d) for d in request.documents),
            max_tokens=request.max_tokens,
        )
        primary, fallbacks = self._router.route(redacted)
        try:
            result = await self._provider(primary.provider).rerank(redacted, primary)
        except DependencyTransientError:
            if not fallbacks:
                raise
            result = await self._provider(fallbacks[0].provider).rerank(redacted, fallbacks[0])
        await self._account(
            request,
            model=result.model,
            provider=result.provider,
            tokens=result.input_tokens,
        )
        return result

    async def _prepare_complete(self, request: ModelRequest) -> ModelRequest:
        messages = list(request.messages)
        schema_name = request.json_schema_name
        if request.template_name:
            template = await self._templates.get(
                request.template_name, request.template_version
            )
            schema_name = schema_name or template.output_schema
            rendered = template.body
            for key, value in request.template_inputs.items():
                rendered = rendered.replace("{{" + key + "}}", str(value))
            messages = [ChatMessage(role="system", content=rendered), *messages]
            if not any(m.role == "user" for m in messages):
                messages.append(
                    ChatMessage(
                        role="user",
                        content=str(request.template_inputs.get("objective", "Proceed.")),
                    )
                )
        redacted = tuple(
            ChatMessage(role=m.role, content=self._redaction.redact(m.content))
            for m in messages
        )
        return ModelRequest(
            tenant_id=request.tenant_id,
            task_id=request.task_id,
            purpose=request.purpose,
            capability=request.capability,
            preferred_tier=request.preferred_tier,
            residency=request.residency,
            messages=redacted,
            template_name=request.template_name,
            template_version=request.template_version,
            template_inputs=dict(request.template_inputs),
            json_schema_name=schema_name,
            max_tokens=request.max_tokens,
        )

    async def _account(
        self,
        request: ModelRequest,
        *,
        model: str,
        provider: str,
        tokens: int,
    ) -> None:
        await self._quotas.consume(request.tenant_id, tokens)
        await self._usage.emit(
            UsageRecord.tokens(
                tenant_id=request.tenant_id,
                task_id=request.task_id,
                model=model,
                provider=provider,
                quantity=tokens,
                purpose=request.purpose,
            )
        )

    def _provider(self, name: str) -> ProviderAdapter:
        return self._providers.get(name)  # type: ignore[return-value]
