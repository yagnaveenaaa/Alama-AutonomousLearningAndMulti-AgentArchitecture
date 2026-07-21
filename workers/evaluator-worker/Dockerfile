FROM python:3.12-slim AS builder

WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY packages/py-alama-common /build/packages/py-alama-common
COPY workers/evaluator-worker /build/workers/evaluator-worker

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir /build/packages/py-alama-common \
    && pip install --no-cache-dir /build/workers/evaluator-worker

FROM python:3.12-slim AS runtime

RUN useradd --create-home --uid 10001 alama
WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY workers/evaluator-worker/migrations /app/migrations
COPY workers/evaluator-worker/alembic.ini /app/alembic.ini

ENV EVALUATOR_WORKER_SERVICE_NAME=evaluator-worker \
    EVALUATOR_WORKER_USE_IN_MEMORY_STORE=false \
    PYTHONUNBUFFERED=1

USER alama

CMD ["evaluator-worker"]
