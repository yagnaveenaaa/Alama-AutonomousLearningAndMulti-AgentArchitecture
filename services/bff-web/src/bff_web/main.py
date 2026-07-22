from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from alama_common.http import register_exception_handlers
from alama_common.logging import configure_logging
from alama_common.otel import configure_opentelemetry, shutdown_opentelemetry
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from strawberry.fastapi import GraphQLRouter

from bff_web.config import BffSettings
from bff_web.container import BffContainer, build_container
from bff_web.schema import schema


async def get_graphql_context(request: Request) -> dict[str, Any]:
    container: BffContainer = request.app.state.container
    auth = container.build_auth(
        subject_id=request.headers.get("x-subject-id"),
        tenant_id=request.headers.get("x-tenant-id"),
        authorization=request.headers.get("authorization"),
    )
    return {
        "request": request,
        "auth": auth,
        "clients": container.clients,
        "loaders": container.build_loaders(auth),
        "settings": container.settings,
    }


def create_app(settings: BffSettings | None = None) -> FastAPI:
    settings = settings or BffSettings()

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
        title="Alama Web BFF",
        version="0.1.0",
        description="GraphQL composition for the web UI (LLD §2.2).",
        lifespan=lifespan,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )
    register_exception_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["ops"])
    async def health() -> JSONResponse:
        return JSONResponse(
            {
                "status": "ok",
                "service": "bff-web",
                "vertical_slice": settings.enable_vertical_slice,
            }
        )

    @app.get("/schema.graphql", tags=["ops"])
    async def schema_sdl() -> PlainTextResponse:
        return PlainTextResponse(str(schema), media_type="text/plain")

    graphql_app = GraphQLRouter(
        schema,
        context_getter=get_graphql_context,  # type: ignore[arg-type]
        graphql_ide="graphiql",
    )
    app.include_router(graphql_app, prefix="/graphql")
    return app


app = create_app()


def run() -> None:
    settings = BffSettings()
    uvicorn.run(
        "bff_web.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    run()
