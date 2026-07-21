from __future__ import annotations

import re
from pathlib import PurePosixPath

from indexing_worker.domain.models import FileClassification, ManifestEntry, SourceFile

_SECRET_PATTERNS = (
    re.compile(r"(?i)api[_-]?key\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)-----BEGIN (RSA |EC )?PRIVATE KEY-----"),
    re.compile(r"(?i)aws_secret_access_key\s*[:=]"),
)

_VENDOR_PREFIXES = ("vendor/", "node_modules/", ".venv/", "dist/", "build/")
_GENERATED_SUFFIXES = (".pb.go", ".generated.py", "_pb2.py", ".min.js")
_DOC_SUFFIXES = (".md", ".rst", ".txt")
_CONFIG_NAMES = {
    "pyproject.toml",
    "setup.cfg",
    "setup.py",
    "requirements.txt",
    "package.json",
    "tsconfig.json",
    ".env.example",
    "Dockerfile",
    "docker-compose.yml",
}
_BINARY_SUFFIXES = (
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".pdf",
    ".zip",
    ".gz",
    ".whl",
    ".so",
    ".dll",
    ".exe",
)


class RepoClassifier:
    """Classify snapshot files: languages, binaries, secrets, skip (LLD §7.1)."""

    def __init__(self, *, supported_languages: frozenset[str]) -> None:
        self._supported = supported_languages

    def detect_language(self, path: str) -> str | None:
        suffix = PurePosixPath(path).suffix.lower()
        if suffix == ".py":
            return "python"
        if suffix in {".md", ".rst"}:
            return "markdown"
        if suffix in {".toml", ".yaml", ".yml", ".json", ".ini", ".cfg"}:
            return "config"
        return None

    def classify_entry(
        self,
        entry: ManifestEntry,
        content: str | None = None,
    ) -> FileClassification:
        path = entry.path.replace("\\", "/")
        lower = path.lower()
        name = PurePosixPath(path).name

        if any(lower.startswith(p) for p in _VENDOR_PREFIXES):
            return FileClassification.VENDOR
        if any(lower.endswith(s) for s in _GENERATED_SUFFIXES):
            return FileClassification.GENERATED
        if any(lower.endswith(s) for s in _BINARY_SUFFIXES):
            return FileClassification.BINARY
        if content is not None and any(p.search(content) for p in _SECRET_PATTERNS):
            return FileClassification.SECRET_HIT
        suffix = PurePosixPath(path).suffix.lower()
        if name in _CONFIG_NAMES or suffix in {".toml", ".yaml", ".yml", ".json", ".ini", ".cfg"}:
            return FileClassification.CONFIG
        if any(lower.endswith(s) for s in _DOC_SUFFIXES):
            return FileClassification.DOC

        language = entry.language or self.detect_language(path)
        if language is None:
            return FileClassification.SKIP
        if language not in self._supported and language not in {"markdown", "config"}:
            # Unsupported languages still get line-window chunking later; keep as source.
            return FileClassification.SOURCE
        return FileClassification.SOURCE

    def classify_file(self, file: SourceFile) -> SourceFile:
        classification = self.classify_entry(
            ManifestEntry(
                path=file.path,
                content_hash=file.content_hash,
                size_bytes=len(file.content.encode("utf-8")),
                language=file.language,
            ),
            content=file.content,
        )
        return SourceFile(
            path=file.path,
            content=file.content,
            content_hash=file.content_hash,
            language=file.language or self.detect_language(file.path),
            classification=classification,
        )

    def size_tier(self, total_bytes: int) -> str:
        if total_bytes < 5_000_000:
            return "hot"
        if total_bytes < 50_000_000:
            return "warm"
        return "cold"
