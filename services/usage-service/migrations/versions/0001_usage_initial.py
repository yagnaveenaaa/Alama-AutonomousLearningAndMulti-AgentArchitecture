"""# Usage schema — initial revision (LLD §4.8)

Revision ID: 0001_usage_initial
Revises:
Create Date: 2026-07-21
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_usage_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "usage_ledger",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("quantity", sa.BigInteger(), nullable=False),
        sa.Column("unit", sa.String(32), nullable=False),
        sa.Column("price_version", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "tenant_id", "idempotency_key", name="uq_usage_ledger_idempotency"
        ),
    )
    op.create_index(
        "ix_usage_ledger_tenant_created",
        "usage_ledger",
        ["tenant_id", "created_at"],
    )

    op.create_table(
        "budgets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("period", sa.String(32), nullable=False),
        sa.Column("limit_usd_micros", sa.BigInteger(), nullable=False),
        sa.Column("limit_tokens", sa.BigInteger(), nullable=False),
        sa.Column("soft_pct", sa.Float(), nullable=False),
        sa.Column("hard_stop", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("spent_usd_micros", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("spent_tokens", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column(
            "reserved_usd_micros", sa.BigInteger(), nullable=False, server_default="0"
        ),
        sa.Column("reserved_tokens", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("tenant_id", "period", name="uq_budgets_tenant_period"),
    )


def downgrade() -> None:
    op.drop_table("budgets")
    op.drop_index("ix_usage_ledger_tenant_created", table_name="usage_ledger")
    op.drop_table("usage_ledger")
