from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from alama_common.context.request import RequestContext, bind_request_context, reset_request_context
from alama_common.errors.types import NotFoundError
from alama_common.http.exception_handlers import register_exception_handlers
from alama_common.ids.uuid7 import new_uuid7


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        token = bind_request_context(
            RequestContext(request_id=new_uuid7(), trace_id="trace-1")
        )
        try:
            return await call_next(request)
        finally:
            reset_request_context(token)


def test_fastapi_exception_handler_returns_standard_envelope() -> None:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)

    @app.get("/items/{item_id}")
    def get_item(item_id: str) -> dict[str, str]:
        raise NotFoundError("Item not found", details={"item_id": item_id})

    client = TestClient(app)
    response = client.get("/items/123")

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "not_found"
    assert body["error"]["message"] == "Item not found"
    assert body["error"]["details"]["item_id"] == "123"
    assert body["error"]["request_id"] is not None
    assert body["error"]["trace_id"] == "trace-1"
