FROM python:3.12-slim AS builder

WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY packages/py-alama-common /build/packages/py-alama-common
COPY services/api-gateway /build/services/api-gateway

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir /build/packages/py-alama-common[fastapi] \
    && pip install --no-cache-dir /build/services/api-gateway

FROM python:3.12-slim AS runtime

RUN useradd --create-home --uid 10001 alama
WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY services/api-gateway/openapi.yaml /app/openapi.yaml

ENV GATEWAY_SERVICE_NAME=api-gateway \
    GATEWAY_HOST=0.0.0.0 \
    GATEWAY_PORT=8080 \
    GATEWAY_USE_ECHO_UPSTREAM=true \
    PYTHONUNBUFFERED=1

USER alama
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health')"

CMD ["uvicorn", "api_gateway.main:app", "--host", "0.0.0.0", "--port", "8080"]
