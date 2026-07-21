from __future__ import annotations

import asyncio
import signal

from alama_common.logging import configure_logging
from alama_common.otel import configure_opentelemetry, shutdown_opentelemetry

from indexing_worker.config import IndexingWorkerSettings
from indexing_worker.container import IndexingWorkerContainer, build_container
from indexing_worker.domain.models import IndexJob


async def process_one(container: IndexingWorkerContainer) -> bool:
    """Dequeue and index a single job. Returns False if queue empty."""
    job = await container.queue.dequeue()
    if job is None:
        return False
    await container.pipeline.run(job)
    return True


async def run_worker_loop(
    container: IndexingWorkerContainer,
    *,
    stop_event: asyncio.Event | None = None,
) -> None:
    stop = stop_event or asyncio.Event()
    while not stop.is_set():
        worked = await process_one(container)
        if not worked:
            try:
                await asyncio.wait_for(
                    stop.wait(),
                    timeout=container.settings.poll_interval_seconds,
                )
            except TimeoutError:
                continue


def create_container(settings: IndexingWorkerSettings | None = None) -> IndexingWorkerContainer:
    return build_container(settings)


async def _async_main() -> None:
    settings = IndexingWorkerSettings()
    configure_logging(
        service_name=settings.service_name,
        environment=settings.environment,
        log_level=settings.log_level,
    )
    configure_opentelemetry(
        service_name=settings.service_name,
        environment=settings.environment,
        cell_id=settings.cell_id,
        region=settings.region,
        enabled=settings.otel_enabled,
        exporter_endpoint=settings.otel_exporter_endpoint,
        sample_ratio=settings.otel_sample_ratio,
    )
    container = build_container(settings)
    stop = asyncio.Event()

    def _handle_stop(*_: object) -> None:
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle_stop)
        except NotImplementedError:
            # Windows: signal handlers limited
            signal.signal(sig, lambda *_a: _handle_stop())

    try:
        await run_worker_loop(container, stop_event=stop)
    finally:
        shutdown_opentelemetry()


def run() -> None:
    asyncio.run(_async_main())


# Re-export for tests / composition
__all__ = [
    "IndexJob",
    "create_container",
    "process_one",
    "run",
    "run_worker_loop",
]


if __name__ == "__main__":
    run()
