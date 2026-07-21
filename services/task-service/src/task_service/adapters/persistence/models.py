from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TaskRow(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        Index("ix_tasks_tenant_state_created", "tenant_id", "state", "created_at"),
        Index("ix_tasks_tenant_repo_created", "tenant_id", "repository_id", "created_at"),
        UniqueConstraint("workflow_id", name="uq_tasks_workflow_id"),
        Index("ix_tasks_created_by_created", "created_by", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    repository_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    created_by: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    workflow_id: Mapped[str] = mapped_column(Text, nullable=False)
    run_id: Mapped[str] = mapped_column(Text, nullable=False, default="")
    base_commit_sha: Mapped[str] = mapped_column(String(40), nullable=False)
    branch_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    pr_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    budget_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False)
    budget_usd_micros: Mapped[int] = mapped_column(BigInteger, nullable=False)
    policy_version: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    parent_task_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    paused: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class TaskEventRow(Base):
    __tablename__ = "task_events"
    __table_args__ = (
        UniqueConstraint("task_id", "sequence", name="uq_task_events_task_sequence"),
        Index("ix_task_events_tenant_created", "tenant_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    task_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tasks.id"),
        nullable=False,
    )
    sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_inline: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    actor_type: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_id: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ApprovalRow(Base):
    __tablename__ = "approvals"
    __table_args__ = (
        Index("ix_approvals_task_status", "task_id", "status"),
        Index("ix_approvals_tenant_status_requested", "tenant_id", "status", "requested_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    task_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tasks.id"),
        nullable=False,
    )
    gate: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    policy_version: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class OutboxEventRow(Base):
    __tablename__ = "outbox_events"
    __table_args__ = (Index("ix_outbox_unpublished", "published_at"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    aggregate_type: Mapped[str] = mapped_column(Text, nullable=False)
    aggregate_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
