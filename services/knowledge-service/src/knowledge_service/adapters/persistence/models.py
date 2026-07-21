from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ConversationRow(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        Index("ix_conversations_tenant_updated", "tenant_id", "updated_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    task_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    repository_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MessageRow(Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("conversation_id", "sequence", name="uq_messages_conversation_sequence"),
        Index("ix_messages_tenant_conversation", "tenant_id", "conversation_id"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    conversation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content_ref: Mapped[str] = mapped_column(Text, nullable=False)
    token_estimate: Mapped[int] = mapped_column(Integer, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MemoryItemRow(Base):
    __tablename__ = "memory_items"
    __table_args__ = (
        Index("ix_memory_items_tenant_scope_status", "tenant_id", "scope", "status"),
        Index("ix_memory_items_tenant_repo_status", "tenant_id", "repository_id", "status"),
        Index(
            "ix_memory_items_expires",
            "expires_at",
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uq_memory_items_tenant_content_hash_active",
            "tenant_id",
            "content_hash",
            unique=True,
            postgresql_where=text("status = 'active' AND deleted_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    scope: Mapped[str] = mapped_column(String(32), nullable=False)
    memory_type: Mapped[str] = mapped_column(String(64), nullable=False)
    repository_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    subject_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    task_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content_ref: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    acl: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    embedding_model: Mapped[str | None] = mapped_column(Text, nullable=True)
    vector_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    legal_hold: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
