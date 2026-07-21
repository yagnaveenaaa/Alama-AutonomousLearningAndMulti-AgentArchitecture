FROM python:3.12-slim AS builder

WORKDIR /build
COPY packages/py-alama-common /build/packages/py-alama-common
COPY services/tool-gateway /build/services/tool-gateway
RUN pip install --no-cache-dir /build/packages/py-alama-common[fastapi] \
    && pip install --no-cache-dir /build/services/tool-gateway

FROM python:3.12-slim AS runtime
RUN useradd --create-home --uid 10001 alama
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY services/tool-gateway/openapi.yaml /app/openapi.yaml
ENV TOOL_GATEWAY_HOST=0.0.0.0 TOOL_GATEWAY_PORT=8108 PYTHONUNBUFFERED=1
USER alama
EXPOSE 8108
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8108/health')"
CMD ["uvicorn", "tool_gateway.main:app", "--host", "0.0.0.0", "--port", "8108"]
