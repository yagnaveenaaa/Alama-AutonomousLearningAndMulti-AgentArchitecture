from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class IndexGenerationRow(Base):
    __tablename__ = "index_generations"
    __table_args__ = (
        Index("ix_index_generations_repo_state", "repository_id", "state"),
        Index("ix_index_generations_tenant_created", "tenant_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    repository_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    snapshot_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    commit_sha: Mapped[str] = mapped_column(String(40), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    embedding_model: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_dim: Mapped[int] = mapped_column(Integer, nullable=False)
    vector_namespace: Mapped[str] = mapped_column(Text, nullable=False)
    lexical_index_name: Mapped[str] = mapped_column(Text, nullable=False)
    stats: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SymbolNodeRow(Base):
    __tablename__ = "symbol_nodes"
    __table_args__ = (
        Index("ix_symbol_nodes_generation_qname", "generation_id", "qualified_name"),
        Index("ix_symbol_nodes_generation_path", "generation_id", "path"),
        Index("ix_symbol_nodes_repository_name", "repository_id", "name"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    repository_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    generation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("index_generations.id"),
        nullable=False,
    )
    language: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    qualified_name: Mapped[str] = mapped_column(Text, nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)


class SymbolEdgeRow(Base):
    __tablename__ = "symbol_edges"
    __table_args__ = (
        Index("ix_symbol_edges_src", "generation_id", "src_symbol_id", "edge_type"),
        Index("ix_symbol_edges_dst", "generation_id", "dst_symbol_id", "edge_type"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    generation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("index_generations.id"),
        nullable=False,
    )
    src_symbol_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("symbol_nodes.id"),
        nullable=False,
    )
    dst_symbol_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("symbol_nodes.id"),
        nullable=False,
    )
    edge_type: Mapped[str] = mapped_column(Text, nullable=False)


class DependencyPackageRow(Base):
    __tablename__ = "dependency_packages"
    __table_args__ = (
        Index("ix_dependency_packages_gen_eco_name", "generation_id", "ecosystem", "name"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    generation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("index_generations.id"),
        nullable=False,
    )
    ecosystem: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(Text, nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
