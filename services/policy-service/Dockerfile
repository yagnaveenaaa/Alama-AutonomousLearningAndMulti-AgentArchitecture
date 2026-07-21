FROM python:3.12-slim AS builder

WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY packages/py-alama-common /build/packages/py-alama-common
COPY services/policy-service /build/services/policy-service

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir /build/packages/py-alama-common[fastapi] \
    && pip install --no-cache-dir /build/services/policy-service

FROM python:3.12-slim AS runtime

RUN useradd --create-home --uid 10001 alama
WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY services/policy-service/migrations /app/migrations
COPY services/policy-service/alembic.ini /app/alembic.ini
COPY services/policy-service/openapi.yaml /app/openapi.yaml

ENV POLICY_SERVICE_NAME=policy-service \
    POLICY_HOST=0.0.0.0 \
    POLICY_PORT=8104 \
    POLICY_USE_IN_MEMORY_STORE=false \
    PYTHONUNBUFFERED=1

USER alama
EXPOSE 8104

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8104/health')"

CMD ["uvicorn", "policy_service.main:app", "--host", "0.0.0.0", "--port", "8104"]
