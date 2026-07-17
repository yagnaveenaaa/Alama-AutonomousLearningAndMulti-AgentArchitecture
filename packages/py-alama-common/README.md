# py-alama-common

Shared Python primitives for all Alama backend services and workers.

## Purpose

This package centralizes cross-cutting platform concerns defined in the Low-Level Design:

- **errors** — Typed exception taxonomy and standard API error envelope (LLD §3.2)
- **auth** — `Principal` value object for authenticated callers (LLD §2.1)
- **logging** — Structured JSON logging with request context (LLD §24)
- **otel** — OpenTelemetry tracer bootstrap (LLD §12.1)
- **config** — `BaseServiceSettings` for validated environment configuration (LLD §3.1)
- **context** — `RequestContext` via contextvars (tenant, request_id, trace_id)
- **retry** — Named retry policies aligned with LLD §3.3
- **pagination** — Cursor encode/decode helpers (LLD §5.1)
- **ids** — UUIDv7 generation (LLD §4.1)
- **http** — FastAPI exception handler registration (optional extra)

## Installation

From the monorepo root:

```bash
pip install -e "packages/py-alama-common[dev]"
```

## Usage

```python
from alama_common import (
    BaseServiceSettings,
    Principal,
    ValidationError,
    configure_logging,
    configure_opentelemetry,
    new_uuid7,
)
```

### FastAPI integration

```python
from fastapi import FastAPI
from alama_common.http import register_exception_handlers

app = FastAPI()
register_exception_handlers(app)
```

## Testing

```bash
cd packages/py-alama-common
pytest
mypy src
ruff check src tests
```

## Ownership

- **Team:** Platform
- **SLO impact:** All services depend on this package; breaking changes require coordinated releases.

## Docker

Not required — this is a library package consumed by service images.

## OpenAPI

Not applicable — no HTTP server is exposed by this package.
