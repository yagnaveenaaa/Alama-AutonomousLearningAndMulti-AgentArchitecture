FROM python:3.12-slim AS builder

WORKDIR /build
COPY packages/py-alama-common /build/packages/py-alama-common
COPY services/model-gateway /build/services/model-gateway
RUN pip install --no-cache-dir /build/packages/py-alama-common[fastapi] \
    && pip install --no-cache-dir /build/services/model-gateway

FROM python:3.12-slim AS runtime
RUN useradd --create-home --uid 10001 alama
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY services/model-gateway/openapi.yaml /app/openapi.yaml
ENV MODEL_GATEWAY_HOST=0.0.0.0 MODEL_GATEWAY_PORT=8107 PYTHONUNBUFFERED=1
USER alama
EXPOSE 8107
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8107/health')"
CMD ["uvicorn", "model_gateway.main:app", "--host", "0.0.0.0", "--port", "8107"]
