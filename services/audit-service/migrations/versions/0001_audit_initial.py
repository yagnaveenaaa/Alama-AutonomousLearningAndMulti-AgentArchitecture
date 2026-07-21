"""# Audit schema — initial revision (LLD §4.8)

Revision ID: 0001_audit_initial
Revises:
Create Date: 2026-07-21
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_audit_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_index",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_type", sa.String(32), nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("resource_type", sa.Text(), nullable=False),
        sa.Column("resource_id", sa.Text(), nullable=False),
        sa.Column("decision", sa.String(32), nullable=False),
        sa.Column("policy_version", sa.Text(), nullable=True),
        sa.Column("object_ref", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("integrity_hash", sa.Text(), nullable=False),
        sa.Column("prev_hash", sa.Text(), nullable=False),
        sa.Column("legal_hold", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_audit_index_tenant_created",
        "audit_index",
        ["tenant_id", "created_at"],
    )
    op.create_index(
        "ix_audit_index_tenant_action_created",
        "audit_index",
        ["tenant_id", "action", "created_at"],
    )
    op.create_table(
        "legal_holds",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("legal_holds")
    op.drop_index("ix_audit_index_tenant_action_created", table_name="audit_index")
    op.drop_index("ix_audit_index_tenant_created", table_name="audit_index")
    op.drop_table("audit_index")
