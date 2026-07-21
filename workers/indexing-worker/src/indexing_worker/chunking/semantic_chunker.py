from __future__ import annotations

import hashlib
import re
from uuid import UUID

from alama_common.ids import new_uuid7

from indexing_worker.domain.models import (
    Chunk,
    ChunkKind,
    FileClassification,
    SourceFile,
    SymbolKind,
    SymbolNode,
)

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


class SemanticChunker:
    """Semantic unit chunking (LLD §7.3)."""

    def __init__(self, *, max_chunk_tokens: int = 1000) -> None:
        self._max_chars = max_chunk_tokens * 4  # rough token≈char/4 budget

    def chunk_file(
        self,
        *,
        file: SourceFile,
        symbols: list[SymbolNode],
        tenant_id: UUID,
        repository_id: UUID,
        generation_id: UUID,
        commit_sha: str,
        embedding_model: str,
        acl_labels: tuple[str, ...] = (),
    ) -> list[Chunk]:
        if file.classification in {
            FileClassification.BINARY,
            FileClassification.SECRET_HIT,
            FileClassification.VENDOR,
            FileClassification.GENERATED,
            FileClassification.SKIP,
        }:
            return []

        if file.classification == FileClassification.DOC or file.language == "markdown":
            return self._chunk_markdown(
                file=file,
                tenant_id=tenant_id,
                repository_id=repository_id,
                generation_id=generation_id,
                commit_sha=commit_sha,
                embedding_model=embedding_model,
                acl_labels=acl_labels,
            )

        if file.classification == FileClassification.CONFIG:
            return [
                self._make_chunk(
                    file=file,
                    text=file.content,
                    start_line=1,
                    end_line=max(1, len(file.content.splitlines())),
                    symbol=None,
                    chunk_kind=ChunkKind.FILE,
                    tenant_id=tenant_id,
                    repository_id=repository_id,
                    generation_id=generation_id,
                    commit_sha=commit_sha,
                    embedding_model=embedding_model,
                    acl_labels=acl_labels,
                    classification=file.classification,
                )
            ]

        symbol_chunks = [
            s
            for s in symbols
            if s.path == file.path
            and s.kind in {SymbolKind.FUNCTION, SymbolKind.METHOD, SymbolKind.CLASS}
        ]
        if symbol_chunks:
            return self._chunk_symbols(
                file=file,
                symbols=symbol_chunks,
                tenant_id=tenant_id,
                repository_id=repository_id,
                generation_id=generation_id,
                commit_sha=commit_sha,
                embedding_model=embedding_model,
                acl_labels=acl_labels,
            )

        return self._line_windows(
            file=file,
            tenant_id=tenant_id,
            repository_id=repository_id,
            generation_id=generation_id,
            commit_sha=commit_sha,
            embedding_model=embedding_model,
            acl_labels=acl_labels,
        )

    def _chunk_symbols(
        self,
        *,
        file: SourceFile,
        symbols: list[SymbolNode],
        tenant_id: UUID,
        repository_id: UUID,
        generation_id: UUID,
        commit_sha: str,
        embedding_model: str,
        acl_labels: tuple[str, ...],
    ) -> list[Chunk]:
        lines = file.content.splitlines()
        chunks: list[Chunk] = []
        for symbol in sorted(symbols, key=lambda s: s.start_line):
            text = "\n".join(lines[symbol.start_line - 1 : symbol.end_line])
            parent = (
                ".".join(symbol.qualified_name.split(".")[:-1])
                if "." in symbol.qualified_name
                else None
            )
            if len(text) <= self._max_chars:
                chunks.append(
                    self._make_chunk(
                        file=file,
                        text=text,
                        start_line=symbol.start_line,
                        end_line=symbol.end_line,
                        symbol=symbol.qualified_name,
                        chunk_kind=ChunkKind.SYMBOL,
                        tenant_id=tenant_id,
                        repository_id=repository_id,
                        generation_id=generation_id,
                        commit_sha=commit_sha,
                        embedding_model=embedding_model,
                        acl_labels=acl_labels,
                        classification=file.classification,
                        parent_qualified_name=parent,
                    )
                )
            else:
                # Large symbol: split by logical blocks with parent qualified_name.
                for start, end, block in self._split_blocks(text, symbol.start_line):
                    chunks.append(
                        self._make_chunk(
                            file=file,
                            text=block,
                            start_line=start,
                            end_line=end,
                            symbol=symbol.qualified_name,
                            chunk_kind=ChunkKind.SYMBOL,
                            tenant_id=tenant_id,
                            repository_id=repository_id,
                            generation_id=generation_id,
                            commit_sha=commit_sha,
                            embedding_model=embedding_model,
                            acl_labels=acl_labels,
                            classification=file.classification,
                            parent_qualified_name=symbol.qualified_name,
                        )
                    )
        return chunks

    def _chunk_markdown(
        self,
        *,
        file: SourceFile,
        tenant_id: UUID,
        repository_id: UUID,
        generation_id: UUID,
        commit_sha: str,
        embedding_model: str,
        acl_labels: tuple[str, ...],
    ) -> list[Chunk]:
        content = file.content
        matches = list(_HEADING_RE.finditer(content))
        if not matches:
            return [
                self._make_chunk(
                    file=file,
                    text=content,
                    start_line=1,
                    end_line=max(1, len(content.splitlines())),
                    symbol=None,
                    chunk_kind=ChunkKind.SECTION,
                    tenant_id=tenant_id,
                    repository_id=repository_id,
                    generation_id=generation_id,
                    commit_sha=commit_sha,
                    embedding_model=embedding_model,
                    acl_labels=acl_labels,
                    classification=FileClassification.DOC,
                )
            ]

        chunks: list[Chunk] = []
        for i, match in enumerate(matches):
            start_char = match.start()
            end_char = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            section = content[start_char:end_char].strip()
            heading = match.group(2).strip()
            start_line = content.count("\n", 0, start_char) + 1
            end_line = content.count("\n", 0, end_char) + 1
            chunks.append(
                self._make_chunk(
                    file=file,
                    text=section,
                    start_line=start_line,
                    end_line=end_line,
                    symbol=heading,
                    chunk_kind=ChunkKind.SECTION,
                    tenant_id=tenant_id,
                    repository_id=repository_id,
                    generation_id=generation_id,
                    commit_sha=commit_sha,
                    embedding_model=embedding_model,
                    acl_labels=acl_labels,
                    classification=FileClassification.DOC,
                )
            )
        return chunks

    def _line_windows(
        self,
        *,
        file: SourceFile,
        tenant_id: UUID,
        repository_id: UUID,
        generation_id: UUID,
        commit_sha: str,
        embedding_model: str,
        acl_labels: tuple[str, ...],
    ) -> list[Chunk]:
        lines = file.content.splitlines()
        if not lines:
            return []
        window = max(20, self._max_chars // 40)
        overlap = max(2, window // 10)
        chunks: list[Chunk] = []
        start = 0
        while start < len(lines):
            end = min(len(lines), start + window)
            text = "\n".join(lines[start:end])
            chunks.append(
                self._make_chunk(
                    file=file,
                    text=text,
                    start_line=start + 1,
                    end_line=end,
                    symbol=None,
                    chunk_kind=ChunkKind.LINE_WINDOW,
                    tenant_id=tenant_id,
                    repository_id=repository_id,
                    generation_id=generation_id,
                    commit_sha=commit_sha,
                    embedding_model=embedding_model,
                    acl_labels=acl_labels,
                    classification=file.classification,
                )
            )
            if end >= len(lines):
                break
            start = end - overlap
        return chunks

    def _split_blocks(self, text: str, base_line: int) -> list[tuple[int, int, str]]:
        lines = text.splitlines()
        blocks: list[tuple[int, int, str]] = []
        start = 0
        while start < len(lines):
            end = min(len(lines), start + max(10, self._max_chars // 40))
            block = "\n".join(lines[start:end])
            blocks.append((base_line + start, base_line + end - 1, block))
            start = end
        return blocks

    def _make_chunk(
        self,
        *,
        file: SourceFile,
        text: str,
        start_line: int,
        end_line: int,
        symbol: str | None,
        chunk_kind: ChunkKind,
        tenant_id: UUID,
        repository_id: UUID,
        generation_id: UUID,
        commit_sha: str,
        embedding_model: str,
        acl_labels: tuple[str, ...],
        classification: FileClassification,
        parent_qualified_name: str | None = None,
    ) -> Chunk:
        return Chunk(
            id=new_uuid7(),
            tenant_id=tenant_id,
            repository_id=repository_id,
            generation_id=generation_id,
            commit_sha=commit_sha,
            path=file.path,
            symbol=symbol,
            language=file.language,
            acl_labels=acl_labels,
            classification=classification,
            content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            embedding_model=embedding_model,
            chunk_kind=chunk_kind,
            text=text,
            start_line=start_line,
            end_line=end_line,
            parent_qualified_name=parent_qualified_name,
        )
