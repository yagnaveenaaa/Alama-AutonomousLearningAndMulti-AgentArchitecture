from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class EvalJobRow(Base):
    """eval.eval_jobs."""

    __tablename__ = "eval_jobs"
    __table_args__ = (
        Index("ix_eval_jobs_tenant_created", "tenant_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    suite_version: Mapped[str] = mapped_column(String(64), nullable=False)
    candidate_ref: Mapped[str] = mapped_column(Text, nullable=False)
    baseline_scorecard_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ScorecardRow(Base):
    """eval.scorecards."""

    __tablename__ = "scorecards"
    __table_args__ = (
        Index("ix_scorecards_tenant_kind", "tenant_id", "kind", "suite_version"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    job_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    suite_version: Mapped[str] = mapped_column(String(64), nullable=False)
    candidate_ref: Mapped[str] = mapped_column(Text, nullable=False)
    metrics: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class GateDecisionRow(Base):
    """eval.gate_decisions."""

    __tablename__ = "gate_decisions"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    scorecard_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    baseline_scorecard_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    reasons: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
