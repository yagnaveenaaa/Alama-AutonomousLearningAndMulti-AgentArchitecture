from __future__ import annotations

from typing import Any
from uuid import UUID

from task_service.domain.models import ActorType, TaskEvent
from task_service.domain.repositories import TaskEventRepository


class TaskEventProjector:
    """Append ordered events; externalize large payloads via payload_ref (LLD §2.5)."""

    def __init__(self, events: TaskEventRepository) -> None:
        self._events = events

    async def project(
        self,
        *,
        tenant_id: UUID,
        task_id: UUID,
        event_type: str,
        actor_type: ActorType,
        actor_id: str,
        payload: dict[str, Any] | None = None,
        externalize_threshold: int = 8_192,
    ) -> TaskEvent:
        sequence = await self._events.next_sequence(task_id)
        payload_inline: dict[str, Any] | None = payload
        payload_ref: str | None = None
        if payload is not None and len(str(payload)) > externalize_threshold:
            payload_ref = f"task-events/{task_id}/{sequence}.json"
            payload_inline = None
        event = TaskEvent.append(
            tenant_id=tenant_id,
            task_id=task_id,
            sequence=sequence,
            event_type=event_type,
            actor_type=actor_type,
            actor_id=actor_id,
            payload_inline=payload_inline,
            payload_ref=payload_ref,
        )
        await self._events.append(event)
        return event
