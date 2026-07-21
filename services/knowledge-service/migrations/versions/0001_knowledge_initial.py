"""# Knowledge schema — initial revision (LLD §4.6)

Revision ID: 0001_knowledge_initial
Revises:
Create Date: 2026-07-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_knowledge_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("repository_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_conversations_tenant_updated",
        "conversations",
        ["tenant_id", "updated_at"],
    )

    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id"),
            nullable=False,
        ),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("content_ref", sa.Text(), nullable=False),
        sa.Column("token_estimate", sa.Integer(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "conversation_id", "sequence", name="uq_messages_conversation_sequence"
        ),
    )
    op.create_index(
        "ix_messages_tenant_conversation",
        "messages",
        ["tenant_id", "conversation_id"],
    )

    op.create_table(
        "memory_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope", sa.String(32), nullable=False),
        sa.Column("memory_type", sa.String(64), nullable=False),
        sa.Column("repository_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("content_ref", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("provenance", postgresql.JSONB(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("acl", postgresql.JSONB(), nullable=False),
        sa.Column("embedding_model", sa.Text(), nullable=True),
        sa.Column("vector_ref", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("legal_hold", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_memory_items_tenant_scope_status",
        "memory_items",
        ["tenant_id", "scope", "status"],
    )
    op.create_index(
        "ix_memory_items_tenant_repo_status",
        "memory_items",
        ["tenant_id", "repository_id", "status"],
    )
    op.create_index(
        "ix_memory_items_expires",
        "memory_items",
        ["expires_at"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "uq_memory_items_tenant_content_hash_active",
        "memory_items",
        ["tenant_id", "content_hash"],
        unique=True,
        postgresql_where=sa.text("status = 'active' AND deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_memory_items_tenant_content_hash_active", table_name="memory_items"
    )
    op.drop_index("ix_memory_items_expires", table_name="memory_items")
    op.drop_index("ix_memory_items_tenant_repo_status", table_name="memory_items")
    op.drop_index("ix_memory_items_tenant_scope_status", table_name="memory_items")
    op.drop_table("memory_items")
    op.drop_index("ix_messages_tenant_conversation", table_name="messages")
    op.drop_table("messages")
    op.drop_index("ix_conversations_tenant_updated", table_name="conversations")
    op.drop_table("conversations")
