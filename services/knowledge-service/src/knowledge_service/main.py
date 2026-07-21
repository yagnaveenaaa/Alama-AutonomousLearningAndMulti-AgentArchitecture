from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from alama_common.http import register_exception_handlers
from alama_common.logging import configure_logging
from alama_common.otel import configure_opentelemetry, shutdown_opentelemetry
from fastapi import FastAPI

from knowledge_service.adapters.http.routes import router
from knowledge_service.config import KnowledgeSettings
from knowledge_service.container import build_container


def create_app(settings: KnowledgeSettings | None = None) -> FastAPI:
    settings = settings or KnowledgeSettings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging(
            service_name=settings.service_name,
            environment=settings.environment,
            log_level=settings.log_level,
        )
        configure_opentelemetry(
            service_name=settings.service_name,
            environment=settings.environment,
            cell_id=settings.cell_id,
            region=settings.region,
            enabled=settings.otel_enabled,
            exporter_endpoint=settings.otel_exporter_endpoint,
            sample_ratio=settings.otel_sample_ratio,
        )
        app.state.container = build_container(settings)
        app.state.settings = settings
        yield
        shutdown_opentelemetry()

    app = FastAPI(
        title="Alama Knowledge Service",
        version="0.1.0",
        description="Governed memory items and conversation threads (LLD §2.8).",
        lifespan=lifespan,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )
    register_exception_handlers(app)
    app.include_router(router)
    return app


app = create_app()


def run() -> None:
    settings = KnowledgeSettings()
    uvicorn.run(
        "knowledge_service.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    run()
