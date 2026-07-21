FROM python:3.12-slim AS builder

WORKDIR /build
COPY packages/py-alama-common /build/packages/py-alama-common
COPY services/retrieval-service /build/services/retrieval-service
RUN pip install --no-cache-dir /build/packages/py-alama-common[fastapi] \
    && pip install --no-cache-dir /build/services/retrieval-service

FROM python:3.12-slim AS runtime
RUN useradd --create-home --uid 10001 alama
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
ENV RETRIEVAL_HOST=0.0.0.0 RETRIEVAL_PORT=8105 RETRIEVAL_USE_IN_MEMORY_STORE=false PYTHONUNBUFFERED=1
USER alama
EXPOSE 8105
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8105/health')"
CMD ["uvicorn", "retrieval_service.main:app", "--host", "0.0.0.0", "--port", "8105"]
