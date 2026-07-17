from __future__ import annotations

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
from opentelemetry.trace import Tracer

_provider: TracerProvider | None = None


def configure_opentelemetry(
    *,
    service_name: str,
    environment: str,
    cell_id: str,
    region: str,
    enabled: bool = True,
    exporter_endpoint: str | None = None,
    sample_ratio: float = 1.0,
) -> None:
    """Initialize OpenTelemetry tracing (LLD §12.1)."""

    global _provider

    if not enabled:
        return

    resource = Resource.create(
        {
            "service.name": service_name,
            "deployment.environment": environment,
            "alama.cell_id": cell_id,
            "alama.region": region,
        }
    )

    sampler = ParentBased(root=TraceIdRatioBased(sample_ratio))
    provider = TracerProvider(resource=resource, sampler=sampler)

    if exporter_endpoint:
        exporter = OTLPSpanExporter(endpoint=exporter_endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))
    elif environment == "development":
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    _provider = provider


def shutdown_opentelemetry() -> None:
    global _provider
    if _provider is not None:
        _provider.shutdown()
        _provider = None


def get_tracer(name: str) -> Tracer:
    return trace.get_tracer(name)
