from __future__ import annotations

from uuid import UUID

from alama_common.auth import Principal
from alama_common.context import RequestContext, bind_request_context
from alama_common.errors import AuthenticationError
from alama_common.ids import new_uuid7
from fastapi import APIRouter, Depends, Header, Request, Response

from usage_service.adapters.http.schemas import (
    AnomalyResponse,
    BudgetListResponse,
    BudgetResponse,
    HealthResponse,
    IngestUsageRequest,
    ReserveBudgetRequest,
    UpsertBudgetRequest,
    UsageRecordResponse,
    UsageSummaryResponse,
)
from usage_service.application.dto import (
    CommitBudgetCommand,
    IngestUsageCommand,
    ReserveBudgetCommand,
    UpsertBudgetCommand,
)
from usage_service.container import UsageContainer
from usage_service.domain.models import Budget, UsageRecord, UsageSummary

router = APIRouter()


def get_container(request: Request) -> UsageContainer:
    return request.app.state.container  # type: ignore[no-any-return]


async def get_principal(
    request: Request,
    x_subject_id: str | None = Header(default=None, alias="X-Subject-Id"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> Principal:
    if x_subject_id is None or x_tenant_id is None:
        raise AuthenticationError("Missing identity headers")
    try:
        subject_id = UUID(x_subject_id)
        tenant_id = UUID(x_tenant_id)
    except ValueError as exc:
        raise AuthenticationError("Invalid identity headers") from exc
    principal = Principal(
        subject_id=subject_id,
        tenant_ids=(tenant_id,),
        scopes=frozenset({"usage:read", "usage:write"}),
    )
    bind_request_context(
        RequestContext(
            request_id=new_uuid7(),
            tenant_id=tenant_id,
            principal=principal,
            trace_id=request.headers.get("traceparent"),
        )
    )
    return principal


def _record_response(record: UsageRecord, *, created: bool) -> UsageRecordResponse:
    return UsageRecordResponse(
        id=record.id,
        tenant_id=record.tenant_id,
        task_id=record.task_id,
        category=record.category.value,
        quantity=record.quantity,
        unit=record.unit.value,
        price_version=record.price_version,
        provider=record.provider,
        model=record.model,
        idempotency_key=record.idempotency_key,
        created_at=record.created_at,
        created=created,
    )


def _budget_response(budget: Budget) -> BudgetResponse:
    return BudgetResponse(
        id=budget.id,
        tenant_id=budget.tenant_id,
        period=budget.period.value,
        limit_usd_micros=budget.limit_usd_micros,
        limit_tokens=budget.limit_tokens,
        soft_pct=budget.soft_pct,
        hard_stop=budget.hard_stop,
        spent_usd_micros=budget.spent_usd_micros,
        spent_tokens=budget.spent_tokens,
        reserved_usd_micros=budget.reserved_usd_micros,
        reserved_tokens=budget.reserved_tokens,
        soft_warning=budget.soft_warning(),
        updated_at=budget.updated_at,
    )


def _summary_response(summary: UsageSummary) -> UsageSummaryResponse:
    return UsageSummaryResponse(
        tenant_id=summary.tenant_id,
        period=summary.period,
        tokens_used=summary.tokens_used,
        tokens_budget=summary.tokens_budget,
        usd_micros_used=summary.usd_micros_used,
        usd_micros_budget=summary.usd_micros_budget,
        soft_warning=summary.soft_warning,
        by_category=dict(summary.by_category),
        anomalies=[
            AnomalyResponse(
                category=a.category.value,
                ratio=a.ratio,
                baseline=a.baseline,
                current=a.current,
                detected_at=a.detected_at,
                message=a.message,
            )
            for a in summary.anomalies
        ],
    )


@router.get("/health", response_model=HealthResponse, tags=["ops"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="usage-service")


@router.post(
    "/v1/usage/events",
    response_model=UsageRecordResponse,
    tags=["usage"],
)
async def ingest_usage(
    body: IngestUsageRequest,
    response: Response,
    principal: Principal = Depends(get_principal),
    container: UsageContainer = Depends(get_container),
) -> UsageRecordResponse:
    record, created = await container.ingestor.ingest(
        IngestUsageCommand(
            tenant_id=principal.primary_tenant_id(),
            category=body.category,
            quantity=body.quantity,
            unit=body.unit,
            price_version=body.price_version,
            provider=body.provider,
            idempotency_key=body.idempotency_key,
            task_id=body.task_id,
            model=body.model,
            enforce_budget=body.enforce_budget,
        )
    )
    response.status_code = 201 if created else 200
    return _record_response(record, created=created)


@router.get(
    "/v1/usage/summary",
    response_model=UsageSummaryResponse,
    tags=["usage"],
)
async def usage_summary(
    principal: Principal = Depends(get_principal),
    container: UsageContainer = Depends(get_container),
) -> UsageSummaryResponse:
    summary = await container.summary.summarize(principal.primary_tenant_id())
    return _summary_response(summary)


@router.get(
    "/v1/usage/budgets",
    response_model=BudgetListResponse,
    tags=["usage"],
)
async def list_budgets(
    principal: Principal = Depends(get_principal),
    container: UsageContainer = Depends(get_container),
) -> BudgetListResponse:
    items = await container.budgets.list_budgets(principal.primary_tenant_id())
    return BudgetListResponse(items=[_budget_response(item) for item in items])


@router.put(
    "/v1/usage/budgets",
    response_model=BudgetResponse,
    tags=["usage"],
)
async def upsert_budget(
    body: UpsertBudgetRequest,
    principal: Principal = Depends(get_principal),
    container: UsageContainer = Depends(get_container),
) -> BudgetResponse:
    budget = await container.budgets.upsert(
        UpsertBudgetCommand(
            tenant_id=principal.primary_tenant_id(),
            period=body.period,
            limit_usd_micros=body.limit_usd_micros,
            limit_tokens=body.limit_tokens,
            soft_pct=body.soft_pct,
            hard_stop=body.hard_stop,
        )
    )
    return _budget_response(budget)


@router.post(
    "/v1/usage/budgets/reserve",
    response_model=BudgetResponse,
    tags=["usage"],
)
async def reserve_budget(
    body: ReserveBudgetRequest,
    principal: Principal = Depends(get_principal),
    container: UsageContainer = Depends(get_container),
) -> BudgetResponse:
    budget = await container.budgets.reserve(
        ReserveBudgetCommand(
            tenant_id=principal.primary_tenant_id(),
            tokens=body.tokens,
            usd_micros=body.usd_micros,
            period=body.period,
        )
    )
    return _budget_response(budget)


@router.post(
    "/v1/usage/budgets/commit",
    response_model=BudgetResponse,
    tags=["usage"],
)
async def commit_budget(
    body: ReserveBudgetRequest,
    principal: Principal = Depends(get_principal),
    container: UsageContainer = Depends(get_container),
) -> BudgetResponse:
    budget = await container.budgets.commit(
        CommitBudgetCommand(
            tenant_id=principal.primary_tenant_id(),
            tokens=body.tokens,
            usd_micros=body.usd_micros,
            period=body.period,
        )
    )
    return _budget_response(budget)
