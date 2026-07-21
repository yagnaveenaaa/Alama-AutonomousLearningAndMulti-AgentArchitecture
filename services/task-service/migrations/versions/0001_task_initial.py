"""# Task schema — initial revision (LLD §4.5)

Revision ID: 0001_task_initial
Revises:
Create Date: 2026-07-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_task_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("repository_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("workflow_id", sa.Text(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False, server_default=""),
        sa.Column("base_commit_sha", sa.String(40), nullable=False),
        sa.Column("branch_name", sa.Text(), nullable=True),
        sa.Column("pr_url", sa.Text(), nullable=True),
        sa.Column("budget_tokens", sa.BigInteger(), nullable=False),
        sa.Column("budget_usd_micros", sa.BigInteger(), nullable=False),
        sa.Column("policy_version", sa.Text(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("parent_task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("paused", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("workflow_id", name="uq_tasks_workflow_id"),
    )
    op.create_index(
        "ix_tasks_tenant_state_created",
        "tasks",
        ["tenant_id", "state", "created_at"],
    )
    op.create_index(
        "ix_tasks_tenant_repo_created",
        "tasks",
        ["tenant_id", "repository_id", "created_at"],
    )
    op.create_index("ix_tasks_created_by_created", "tasks", ["created_by", "created_at"])

    op.create_table(
        "task_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tasks.id"),
            nullable=False,
        ),
        sa.Column("sequence", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("payload_ref", sa.Text(), nullable=True),
        sa.Column("payload_inline", postgresql.JSONB(), nullable=True),
        sa.Column("actor_type", sa.String(16), nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("task_id", "sequence", name="uq_task_events_task_sequence"),
    )
    op.create_index(
        "ix_task_events_tenant_created",
        "task_events",
        ["tenant_id", "created_at"],
    )

    op.create_table(
        "approvals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tasks.id"),
            nullable=False,
        ),
        sa.Column("gate", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("policy_version", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
    )
    op.create_index("ix_approvals_task_status", "approvals", ["task_id", "status"])
    op.create_index(
        "ix_approvals_tenant_status_requested",
        "approvals",
        ["tenant_id", "status", "requested_at"],
    )

    op.create_table(
        "outbox_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("aggregate_type", sa.Text(), nullable=False),
        sa.Column("aggregate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_outbox_unpublished", "outbox_events", ["published_at"])


def downgrade() -> None:
    op.drop_table("outbox_events")
    op.drop_table("approvals")
    op.drop_table("task_events")
    op.drop_table("tasks")
