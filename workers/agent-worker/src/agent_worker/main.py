from __future__ import annotations

import asyncio
import signal

from alama_common.logging import configure_logging
from alama_common.otel import configure_opentelemetry, shutdown_opentelemetry

from agent_worker.config import AgentWorkerSettings
from agent_worker.container import AgentWorkerContainer, build_container
from agent_worker.workflows.agent_workflow import AgentWorkflowInput


async def process_one(container: AgentWorkerContainer) -> bool:
    if not container.jobs:
        return False
    job = container.jobs.pop(0)
    await container.runtime.start(job)
    return True


async def run_worker_loop(
    container: AgentWorkerContainer,
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


def enqueue(container: AgentWorkerContainer, job: AgentWorkflowInput) -> None:
    container.jobs.append(job)


async def _async_main() -> None:
    settings = AgentWorkerSettings()
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


if __name__ == "__main__":
    run()
