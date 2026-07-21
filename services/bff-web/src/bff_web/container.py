from __future__ import annotations

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
    tasks = InMemoryTaskClient()
    clients = ServiceClients(
        tasks=tasks,
        repositories=InMemoryRepositoryClient(),
        knowledge=InMemoryKnowledgeClient(tasks, stream_base_url=settings.stream_base_url),
        usage=InMemoryUsageClient(),
    )
    return BffContainer(settings, clients)
