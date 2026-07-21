from __future__ import annotations

import ast
import hashlib
from dataclasses import dataclass
from uuid import UUID

from alama_common.ids import new_uuid7

from indexing_worker.domain.models import (
    EdgeType,
    SourceFile,
    SymbolEdge,
    SymbolKind,
    SymbolNode,
)


@dataclass(frozen=True, slots=True)
class ParseResult:
    nodes: tuple[SymbolNode, ...]
    edges: tuple[SymbolEdge, ...]


class TreeSitterFacade:
    """AST/symbol extraction facade (LLD §7.1 / §7.2).

    First vertical slice: Python only via stdlib ``ast`` (grammar-equivalent
    symbol table). Additional tree-sitter grammars plug in behind this facade.
    """

    def __init__(self, *, supported_languages: frozenset[str]) -> None:
        self._supported = supported_languages

    def parse(
        self,
        *,
        file: SourceFile,
        tenant_id: UUID,
        repository_id: UUID,
        generation_id: UUID,
    ) -> ParseResult:
        language = file.language or "unknown"
        if language == "python" and "python" in self._supported:
            return self._parse_python(
                file=file,
                tenant_id=tenant_id,
                repository_id=repository_id,
                generation_id=generation_id,
            )
        # Unsupported: no AST symbols; chunker falls back to line windows.
        return ParseResult(nodes=(), edges=())

    def _parse_python(
        self,
        *,
        file: SourceFile,
        tenant_id: UUID,
        repository_id: UUID,
        generation_id: UUID,
    ) -> ParseResult:
        try:
            tree = ast.parse(file.content)
        except SyntaxError:
            return ParseResult(nodes=(), edges=())

        module_id = new_uuid7()
        module_hash = hashlib.sha256(file.content.encode("utf-8")).hexdigest()
        lines = file.content.splitlines() or [""]
        module = SymbolNode(
            id=module_id,
            tenant_id=tenant_id,
            repository_id=repository_id,
            generation_id=generation_id,
            language="python",
            kind=SymbolKind.MODULE,
            name=file.path.rsplit("/", 1)[-1],
            qualified_name=file.path.replace("/", ".").removesuffix(".py"),
            path=file.path,
            start_line=1,
            end_line=len(lines),
            content_hash=module_hash,
        )

        nodes: list[SymbolNode] = [module]
        edges: list[SymbolEdge] = []
        qname_to_id: dict[str, UUID] = {module.qualified_name: module_id}

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                qname = f"{module.qualified_name}.{node.name}"
                symbol = self._symbol_from_def(
                    node=node,
                    kind=SymbolKind.CLASS,
                    name=node.name,
                    qualified_name=qname,
                    file=file,
                    tenant_id=tenant_id,
                    repository_id=repository_id,
                    generation_id=generation_id,
                )
                nodes.append(symbol)
                qname_to_id[qname] = symbol.id
                edges.append(
                    SymbolEdge(
                        id=new_uuid7(),
                        generation_id=generation_id,
                        src_symbol_id=module_id,
                        dst_symbol_id=symbol.id,
                        edge_type=EdgeType.REFERENCES,
                    )
                )
                for base in node.bases:
                    base_name = _expr_name(base)
                    if base_name and base_name in qname_to_id:
                        edges.append(
                            SymbolEdge(
                                id=new_uuid7(),
                                generation_id=generation_id,
                                src_symbol_id=symbol.id,
                                dst_symbol_id=qname_to_id[base_name],
                                edge_type=EdgeType.INHERITS,
                            )
                        )

            elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                parent_class = _enclosing_class_name(tree, node)
                if parent_class:
                    qname = f"{module.qualified_name}.{parent_class}.{node.name}"
                    kind = SymbolKind.METHOD
                else:
                    qname = f"{module.qualified_name}.{node.name}"
                    kind = SymbolKind.FUNCTION
                symbol = self._symbol_from_def(
                    node=node,
                    kind=kind,
                    name=node.name,
                    qualified_name=qname,
                    file=file,
                    tenant_id=tenant_id,
                    repository_id=repository_id,
                    generation_id=generation_id,
                )
                nodes.append(symbol)
                qname_to_id[qname] = symbol.id
                edges.append(
                    SymbolEdge(
                        id=new_uuid7(),
                        generation_id=generation_id,
                        src_symbol_id=module_id,
                        dst_symbol_id=symbol.id,
                        edge_type=EdgeType.REFERENCES,
                    )
                )

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    edges.append(
                        self._import_edge(
                            generation_id=generation_id,
                            src_id=module_id,
                            imported=alias.name,
                            qname_to_id=qname_to_id,
                        )
                    )
            elif isinstance(node, ast.ImportFrom) and node.module:
                edges.append(
                    self._import_edge(
                        generation_id=generation_id,
                        src_id=module_id,
                        imported=node.module,
                        qname_to_id=qname_to_id,
                    )
                )

        return ParseResult(nodes=tuple(nodes), edges=tuple(edges))

    def _symbol_from_def(
        self,
        *,
        node: ast.AST,
        kind: SymbolKind,
        name: str,
        qualified_name: str,
        file: SourceFile,
        tenant_id: UUID,
        repository_id: UUID,
        generation_id: UUID,
    ) -> SymbolNode:
        start = getattr(node, "lineno", 1)
        end = getattr(node, "end_lineno", start) or start
        segment = "\n".join(file.content.splitlines()[start - 1 : end])
        return SymbolNode(
            id=new_uuid7(),
            tenant_id=tenant_id,
            repository_id=repository_id,
            generation_id=generation_id,
            language="python",
            kind=kind,
            name=name,
            qualified_name=qualified_name,
            path=file.path,
            start_line=start,
            end_line=end,
            content_hash=hashlib.sha256(segment.encode("utf-8")).hexdigest(),
        )

    def _import_edge(
        self,
        *,
        generation_id: UUID,
        src_id: UUID,
        imported: str,
        qname_to_id: dict[str, UUID],
    ) -> SymbolEdge:
        dst = qname_to_id.get(imported, src_id)
        return SymbolEdge(
            id=new_uuid7(),
            generation_id=generation_id,
            src_symbol_id=src_id,
            dst_symbol_id=dst,
            edge_type=EdgeType.IMPORTS,
        )


def _expr_name(expr: ast.expr) -> str | None:
    if isinstance(expr, ast.Name):
        return expr.id
    if isinstance(expr, ast.Attribute):
        base = _expr_name(expr.value)
        return f"{base}.{expr.attr}" if base else expr.attr
    return None


def _enclosing_class_name(tree: ast.AST, target: ast.AST) -> str | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for child in ast.walk(node):
                if child is target:
                    return node.name
    return None
