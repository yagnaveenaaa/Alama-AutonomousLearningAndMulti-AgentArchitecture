from __future__ import annotations

from pathlib import Path
from uuid import UUID

from alama_common.auth import Principal
from alama_common.errors import AuthenticationError
from alama_common.ids import new_uuid7

from bff_web.auth_context import AuthContext
from bff_web.clients.memory import (
    InMemoryKnowledgeClient,
    InMemoryRepositoryClient,
    InMemoryTaskClient,
    InMemoryUsageClient,
)
from bff_web.clients.ports import ServiceClients
from bff_web.config import BffSettings
from bff_web.dataloaders import DataLoaders


class BffContainer:
    def __init__(self, settings: BffSettings, clients: ServiceClients) -> None:
        self.settings = settings
        self.clients = clients

    def build_auth(
        self,
        *,
        subject_id: str | None,
        tenant_id: str | None,
        authorization: str | None,
    ) -> AuthContext:
        if self.settings.enable_vertical_slice:
            subject_id = subject_id or self.settings.slice_subject_id
            tenant_id = tenant_id or self.settings.slice_tenant_id
        if subject_id is None or tenant_id is None:
            raise AuthenticationError("Missing identity headers")
        try:
            sid = UUID(subject_id)
            tid = UUID(tenant_id)
        except ValueError as exc:
            raise AuthenticationError("Invalid identity headers") from exc
        principal = Principal(
            subject_id=sid,
            tenant_ids=(tid,),
            scopes=frozenset({"web:read", "web:write"}),
        )
        return AuthContext(
            principal=principal,
            tenant_id=tid,
            request_id=new_uuid7(),
            authorization=authorization,
        )

    def build_loaders(self, auth: AuthContext) -> DataLoaders:
        return DataLoaders(self.clients, auth)


def build_container(settings: BffSettings | None = None) -> BffContainer:
    settings = settings or BffSettings()
    if settings.enable_vertical_slice:
        from alama_slice.orchestrator import VerticalSliceOrchestrator
        from bff_web.clients.slice_clients import (
            SliceKnowledgeClient,
            SliceRepositoryClient,
            SliceTaskClient,
            SliceUsageClient,
        )

        fixture = Path(settings.fixture_dir) if settings.fixture_dir else None
        orch = VerticalSliceOrchestrator(fixture_dir=fixture)
        tasks = SliceTaskClient(orch)
        clients = ServiceClients(
            tasks=tasks,
            repositories=SliceRepositoryClient(orch.store),
            knowledge=SliceKnowledgeClient(
                orch, tasks, stream_base_url=settings.stream_base_url
            ),
            usage=SliceUsageClient(),
        )
        return BffContainer(settings, clients)

    tasks = InMemoryTaskClient()
    clients = ServiceClients(
        tasks=tasks,
        repositories=InMemoryRepositoryClient(),
        knowledge=InMemoryKnowledgeClient(tasks, stream_base_url=settings.stream_base_url),
        usage=InMemoryUsageClient(),
    )
    return BffContainer(settings, clients)
