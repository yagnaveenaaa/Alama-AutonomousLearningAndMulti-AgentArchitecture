from __future__ import annotations

import re

_SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?[^\s'\"]{8,}"),
    re.compile(
        r"(?i)-----BEGIN (RSA |EC )?PRIVATE KEY-----"
        r"[\s\S]+?-----END (RSA |EC )?PRIVATE KEY-----"
    ),
    re.compile(r"(?i)ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"(?i)sk-[A-Za-z0-9]{20,}"),
)


class RedactionFilter:
    """Strip secrets before provider egress (LLD §2.9)."""

    def redact(self, text: str) -> str:
        redacted = text
        for pattern in _SECRET_PATTERNS:
            redacted = pattern.sub("[REDACTED]", redacted)
        return redacted

    def redact_messages(
        self, messages: list[tuple[str, str]]
    ) -> list[tuple[str, str]]:
        return [(role, self.redact(content)) for role, content in messages]
