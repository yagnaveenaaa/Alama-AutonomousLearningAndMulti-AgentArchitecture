from __future__ import annotations

from dataclasses import dataclass

from tool_gateway.application.gateway import ToolGatewayService
from tool_gateway.audit.sink import InMemoryAuditSink
from tool_gateway.capabilities.issuer import HmacCapabilityIssuer
from tool_gateway.catalog.registry import ToolSchemaRegistry
from tool_gateway.config import ToolGatewaySettings
from tool_gateway.policy_bridge.bridge import AllowlistPolicyBridge
from tool_gateway.sandbox.executor import InMemorySandboxExecutor


@dataclass
class ToolGatewayContainer:
    settings: ToolGatewaySettings
    gateway: ToolGatewayService
    sandbox: InMemorySandboxExecutor
    audit: InMemoryAuditSink
    catalog: ToolSchemaRegistry


def build_container(settings: ToolGatewaySettings | None = None) -> ToolGatewayContainer:
    settings = settings or ToolGatewaySettings()
    catalog = ToolSchemaRegistry()
    issuer = HmacCapabilityIssuer(
        signing_key=settings.capability_signing_key,
        ttl_seconds=settings.capability_ttl_seconds,
    )
    policy = AllowlistPolicyBridge(catalog, policy_version=settings.policy_version)
    sandbox = InMemorySandboxExecutor()
    audit = InMemoryAuditSink()
    gateway = ToolGatewayService(
        catalog=catalog,
        issuer=issuer,
        policy=policy,
        sandbox=sandbox,
        audit=audit,
        policy_version=settings.policy_version,
        max_output_bytes=settings.max_output_bytes,
    )
    return ToolGatewayContainer(
        settings=settings,
        gateway=gateway,
        sandbox=sandbox,
        audit=audit,
        catalog=catalog,
    )
