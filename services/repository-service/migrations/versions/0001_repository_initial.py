"""# Repository schema — initial revision (LLD §4.4)

Revision ID: 0001_repository_initial
Revises:
Create Date: 2026-07-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_repository_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scm_installations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("external_installation_id", sa.Text(), nullable=False),
        sa.Column("account_login", sa.Text(), nullable=False),
        sa.Column("secret_ref", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "tenant_id",
            "provider",
            "external_installation_id",
            name="uq_scm_installations_tenant_provider_ext",
        ),
    )

    op.create_table(
        "repositories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "installation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scm_installations.id"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("external_repo_id", sa.Text(), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("default_branch", sa.Text(), nullable=False),
        sa.Column("visibility", sa.String(32), nullable=False),
        sa.Column("size_tier", sa.String(16), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "tenant_id",
            "provider",
            "external_repo_id",
            name="uq_repositories_tenant_provider_ext",
        ),
    )
    op.create_index("ix_repositories_tenant_full_name", "repositories", ["tenant_id", "full_name"])
    op.create_index(
        "ix_repositories_tenant_size_tier",
        "repositories",
        ["tenant_id", "size_tier"],
    )

    op.create_table(
        "webhook_deliveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("delivery_id", sa.Text(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("payload_ref", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("provider", "delivery_id", name="uq_webhook_provider_delivery"),
    )
    op.create_index("ix_webhook_status_created", "webhook_deliveries", ["status", "created_at"])

    op.create_table(
        "repo_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "repository_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("repositories.id"),
            nullable=False,
        ),
        sa.Column("commit_sha", sa.String(40), nullable=False),
        sa.Column("parent_commit_sha", sa.String(40), nullable=True),
        sa.Column("manifest_ref", sa.Text(), nullable=False),
        sa.Column("index_generation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("repository_id", "commit_sha", name="uq_snapshots_repo_commit"),
    )
    op.create_index("ix_snapshots_repo_state", "repo_snapshots", ["repository_id", "state"])
    op.create_index("ix_snapshots_tenant_created", "repo_snapshots", ["tenant_id", "created_at"])


def downgrade() -> None:
    op.drop_table("repo_snapshots")
    op.drop_table("webhook_deliveries")
    op.drop_table("repositories")
    op.drop_table("scm_installations")
