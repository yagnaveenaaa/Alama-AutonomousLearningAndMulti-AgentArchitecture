FROM python:3.12-slim AS builder

WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY packages/py-alama-common /build/packages/py-alama-common
COPY services/bff-web /build/services/bff-web

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir /build/packages/py-alama-common[fastapi] \
    && pip install --no-cache-dir /build/services/bff-web

FROM python:3.12-slim AS runtime

RUN useradd --create-home --uid 10001 alama
WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY services/bff-web/schema.graphql /app/schema.graphql

ENV BFF_SERVICE_NAME=bff-web \
    BFF_HOST=0.0.0.0 \
    BFF_PORT=8081 \
    BFF_USE_IN_MEMORY_CLIENTS=true \
    PYTHONUNBUFFERED=1

USER alama
EXPOSE 8081

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8081/health')"

CMD ["uvicorn", "bff_web.main:app", "--host", "0.0.0.0", "--port", "8081"]
