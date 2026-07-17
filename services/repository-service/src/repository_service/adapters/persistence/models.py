from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ScmInstallationRow(Base):
    __tablename__ = "scm_installations"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "provider",
            "external_installation_id",
            name="uq_scm_installations_tenant_provider_ext",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    external_installation_id: Mapped[str] = mapped_column(Text, nullable=False)
    account_login: Mapped[str] = mapped_column(Text, nullable=False)
    secret_ref: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RepositoryRow(Base):
    __tablename__ = "repositories"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "provider",
            "external_repo_id",
            name="uq_repositories_tenant_provider_ext",
        ),
        Index("ix_repositories_tenant_full_name", "tenant_id", "full_name"),
        Index("ix_repositories_tenant_size_tier", "tenant_id", "size_tier"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    installation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("scm_installations.id"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    external_repo_id: Mapped[str] = mapped_column(Text, nullable=False)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    default_branch: Mapped[str] = mapped_column(Text, nullable=False)
    visibility: Mapped[str] = mapped_column(String(32), nullable=False)
    size_tier: Mapped[str] = mapped_column(String(16), nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WebhookDeliveryRow(Base):
    __tablename__ = "webhook_deliveries"
    __table_args__ = (
        UniqueConstraint("provider", "delivery_id", name="uq_webhook_provider_delivery"),
        Index("ix_webhook_status_created", "status", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    delivery_id: Mapped[str] = mapped_column(Text, nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload_ref: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RepoSnapshotRow(Base):
    __tablename__ = "repo_snapshots"
    __table_args__ = (
        UniqueConstraint("repository_id", "commit_sha", name="uq_snapshots_repo_commit"),
        Index("ix_snapshots_repo_state", "repository_id", "state"),
        Index("ix_snapshots_tenant_created", "tenant_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    repository_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("repositories.id"),
        nullable=False,
    )
    commit_sha: Mapped[str] = mapped_column(String(40), nullable=False)
    parent_commit_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)
    manifest_ref: Mapped[str] = mapped_column(Text, nullable=False)
    index_generation_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
