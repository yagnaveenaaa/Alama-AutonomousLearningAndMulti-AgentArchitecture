from __future__ import annotations

from alama_common.context.request import (
    RequestContext,
    bind_request_context,
    get_request_context,
    reset_request_context,
)
from alama_common.ids.uuid7 import new_uuid7


def test_request_context_binding() -> None:
    assert get_request_context() is None

    context = RequestContext(
        request_id=new_uuid7(),
        trace_id="trace-abc",
        tenant_id=new_uuid7(),
        schema_version="v1",
    )
    token = bind_request_context(context)
    try:
        loaded = get_request_context()
        assert loaded is not None
        assert loaded.request_id == context.request_id
        assert loaded.trace_id == "trace-abc"
    finally:
        reset_request_context(token)

    assert get_request_context() is None
