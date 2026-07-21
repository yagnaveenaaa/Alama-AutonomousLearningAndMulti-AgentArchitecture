FROM python:3.12-slim AS builder

WORKDIR /build
COPY packages/py-alama-common /build/packages/py-alama-common
COPY workers/agent-worker /build/workers/agent-worker
RUN pip install --no-cache-dir /build/packages/py-alama-common \
    && pip install --no-cache-dir /build/workers/agent-worker

FROM python:3.12-slim AS runtime
RUN useradd --create-home --uid 10001 alama
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
ENV AGENT_WORKER_SERVICE_NAME=agent-worker \
    AGENT_WORKER_TASK_QUEUE=agent-general \
    AGENT_WORKER_OTEL_ENABLED=false \
    PYTHONUNBUFFERED=1
USER alama
CMD ["agent-worker"]
