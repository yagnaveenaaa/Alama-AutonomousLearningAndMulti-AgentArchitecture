from __future__ import annotations

import json
from uuid import UUID

from alama_common.errors import NotFoundError, ValidationError

# Public path prefixes → logical service (LLD cell services; model/tool stay internal).
_ROUTE_PREFIXES: tuple[tuple[str, str], ...] = (
    ("/v1/tenants", "identity"),
    ("/v1/subjects", "identity"),
    ("/v1/api-keys", "identity"),
    ("/v1/scim", "identity"),
    ("/v1/repos", "repository"),
    ("/v1/installations", "repository"),
    ("/v1/webhooks", "repository"),
    ("/v1/tasks", "task"),
    ("/v1/approvals", "task"),
    ("/v1/policy", "policy"),
    ("/v1/retrieve", "retrieval"),
    ("/v1/memories", "knowledge"),
    ("/v1/conversations", "knowledge"),
)


class StaticTenantRouter:
    """Resolve tenant → cell and path → upstream service URL (LLD §2.1)."""

    def __init__(
        self,
        *,
        tenant_cell_map: dict[UUID, str],
        default_cell_base_url: str,
        service_upstreams: dict[str, str],
    ) -> None:
        self._tenant_cell_map = tenant_cell_map
        self._default_cell = default_cell_base_url.rstrip("/")
        self._upstreams = {k: v.rstrip("/") for k, v in service_upstreams.items()}

    @classmethod
    def from_settings(
        cls,
        *,
        tenant_cell_map_json: str,
        default_cell_base_url: str,
        identity_upstream: str,
        repository_upstream: str,
        task_upstream: str,
        policy_upstream: str,
        retrieval_upstream: str,
        knowledge_upstream: str,
    ) -> StaticTenantRouter:
        raw = json.loads(tenant_cell_map_json or "{}")
        if not isinstance(raw, dict):
            raise ValidationError("tenant_cell_map_json must be a JSON object")
        mapping: dict[UUID, str] = {}
        for key, value in raw.items():
            mapping[UUID(str(key))] = str(value).rstrip("/")
        return cls(
            tenant_cell_map=mapping,
            default_cell_base_url=default_cell_base_url,
            service_upstreams={
                "identity": identity_upstream,
                "repository": repository_upstream,
                "task": task_upstream,
                "policy": policy_upstream,
                "retrieval": retrieval_upstream,
                "knowledge": knowledge_upstream,
            },
        )

    def resolve_cell_base(self, tenant_id: UUID) -> str:
        return self._tenant_cell_map.get(tenant_id, self._default_cell)

    def resolve_service(self, path: str) -> str:
        for prefix, service in _ROUTE_PREFIXES:
            if path == prefix or path.startswith(prefix + "/") or path.startswith(prefix + "?"):
                return service
        raise NotFoundError(f"No upstream route for path {path}")

    def resolve_upstream(self, path: str, tenant_id: UUID) -> tuple[str, str]:
        _ = tenant_id  # cell placement reserved for multi-cell mesh
        service = self.resolve_service(path)
        base = self._upstreams.get(service)
        if base is None:
            raise NotFoundError(f"No upstream configured for service {service}")
        # Local single-cell: route by service host. Multi-cell would use cell base + mesh.
        return base, path
