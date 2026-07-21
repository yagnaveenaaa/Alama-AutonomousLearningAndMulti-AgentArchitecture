from __future__ import annotations

from agent_worker.protocols.artifacts import ArtifactEnvelope, ArtifactType


class AgentMessageBus:
    """In-process typed artifact handoffs — not free chat (LLD §2.15)."""

    def __init__(self) -> None:
        self._log: list[ArtifactEnvelope] = []

    def publish(self, envelope: ArtifactEnvelope) -> ArtifactEnvelope:
        self._log.append(envelope)
        return envelope

    def history(self, *, artifact_type: ArtifactType | None = None) -> list[ArtifactEnvelope]:
        if artifact_type is None:
            return list(self._log)
        return [item for item in self._log if item.artifact_type == artifact_type]

    def clear(self) -> None:
        self._log.clear()
