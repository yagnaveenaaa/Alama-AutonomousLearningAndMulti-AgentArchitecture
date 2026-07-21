from __future__ import annotations

from tool_gateway.domain.models import ToolReceipt


class InMemoryAuditSink:
    """Append-only tool receipt audit log (LLD §2.10 audit module)."""

    def __init__(self) -> None:
        self.receipts: list[ToolReceipt] = []

    async def emit_receipt(self, receipt: ToolReceipt) -> None:
        self.receipts.append(receipt)
