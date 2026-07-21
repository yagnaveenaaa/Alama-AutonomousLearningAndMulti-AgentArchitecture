from __future__ import annotations

import asyncio
import signal

from alama_common.logging import configure_logging
from alama_common.otel import configure_opentelemetry, shutdown_opentelemetry

from evaluator_worker.config import EvaluatorWorkerSettings
from evaluator_worker.container import EvaluatorWorkerContainer, build_container
from evaluator_worker.domain.models import EvalJob


async def process_one(container: EvaluatorWorkerContainer) -> bool:
    """Dequeue and run a single eval job. Returns False if queue empty."""
    job = await container.queue.dequeue()
    if job is None:
        return False
    scorecard, gate = await container.runner.run(job)
    container.store.gates.append(gate)
    del scorecard
    return True


async def run_worker_loop(
    container: EvaluatorWorkerContainer,
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


def create_container(
    settings: EvaluatorWorkerSettings | None = None,
) -> EvaluatorWorkerContainer:
    return build_container(settings)


async def _async_main() -> None:
    settings = EvaluatorWorkerSettings()
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
            signal.signal(sig, lambda *_a: _handle_stop())

    try:
        await run_worker_loop(container, stop_event=stop)
    finally:
        shutdown_opentelemetry()


def run() -> None:
    asyncio.run(_async_main())


__all__ = [
    "EvalJob",
    "create_container",
    "process_one",
    "run",
    "run_worker_loop",
]


if __name__ == "__main__":
    run()
