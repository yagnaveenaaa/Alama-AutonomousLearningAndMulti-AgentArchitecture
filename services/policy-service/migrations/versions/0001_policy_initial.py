"""# Policy schema — initial revision (LLD §4.8)

Revision ID: 0001_policy_initial
Revises:
Create Date: 2026-07-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_policy_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "policy_bundles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("bundle_ref", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("checksum", sa.Text(), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("tenant_id", "version", name="uq_policy_bundles_tenant_version"),
    )
    op.create_index(
        "uq_policy_bundles_one_active",
        "policy_bundles",
        ["tenant_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index(
        "ix_policy_bundles_tenant_status",
        "policy_bundles",
        ["tenant_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_policy_bundles_tenant_status", table_name="policy_bundles")
    op.drop_index("uq_policy_bundles_one_active", table_name="policy_bundles")
    op.drop_table("policy_bundles")
