from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from alama_common.http import register_exception_handlers
from alama_common.logging import configure_logging
from alama_common.otel import configure_opentelemetry, shutdown_opentelemetry
from fastapi import FastAPI

from retrieval_service.adapters.http.routes import router
from retrieval_service.config import RetrievalSettings
from retrieval_service.container import build_container


def create_app(settings: RetrievalSettings | None = None) -> FastAPI:
    settings = settings or RetrievalSettings()

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
        app.state.container = build_container()
        yield
        shutdown_opentelemetry()

    app = FastAPI(
        title="Alama Retrieval Service",
        version="0.1.0",
        description="Commit-consistent hybrid retrieval with ACL filtering and citations.",
        lifespan=lifespan,
    )
    register_exception_handlers(app)
    app.include_router(router)
    return app


app = create_app()


def run() -> None:
    settings = RetrievalSettings()
    uvicorn.run("retrieval_service.main:app", host=settings.host, port=settings.port)


if __name__ == "__main__":
    run()
