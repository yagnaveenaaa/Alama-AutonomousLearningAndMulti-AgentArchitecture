FROM python:3.12-slim AS builder

WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY packages/py-alama-common /build/packages/py-alama-common
COPY services/usage-service /build/services/usage-service

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir /build/packages/py-alama-common[fastapi] \
    && pip install --no-cache-dir /build/services/usage-service

FROM python:3.12-slim AS runtime

RUN useradd --create-home --uid 10001 alama
WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY services/usage-service/migrations /app/migrations
COPY services/usage-service/alembic.ini /app/alembic.ini
COPY services/usage-service/openapi.yaml /app/openapi.yaml

ENV USAGE_SERVICE_NAME=usage-service \
    USAGE_HOST=0.0.0.0 \
    USAGE_PORT=8110 \
    USAGE_USE_IN_MEMORY_STORE=false \
    PYTHONUNBUFFERED=1

USER alama
EXPOSE 8110

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8110/health')"

CMD ["uvicorn", "usage_service.main:app", "--host", "0.0.0.0", "--port", "8110"]
