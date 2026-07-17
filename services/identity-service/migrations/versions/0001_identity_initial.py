"""# Identity schema — initial revision (LLD §4.3)

Revision ID: 0001_identity_initial
Revises:
Create Date: 2026-07-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_identity_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")

    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", postgresql.CITEXT(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("home_region", sa.Text(), nullable=False),
        sa.Column("home_cell", sa.Text(), nullable=False),
        sa.Column("isolation_tier", sa.String(32), nullable=False),
        sa.Column("plan", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("data_residency", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("slug", name="uq_tenants_slug"),
    )
    op.create_index("ix_tenants_home_cell", "tenants", ["home_cell"])
    op.create_index("ix_tenants_status", "tenants", ["status"])

    op.create_table(
        "subjects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("external_idp_sub", sa.Text(), nullable=False),
        sa.Column("email", postgresql.CITEXT(), nullable=True),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("tenant_id", "external_idp_sub", name="uq_subjects_tenant_idp"),
    )
    op.create_index("ix_subjects_tenant_email", "subjects", ["tenant_id", "email"])

    op.create_table(
        "groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_groups_tenant_name"),
    )

    op.create_table(
        "group_members",
        sa.Column("group_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("groups.id"), primary_key=True),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subjects.id"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "role_bindings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subjects.id"), nullable=True),
        sa.Column("group_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("groups.id"), nullable=True),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column(
            "resource_scope",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint(
            "(subject_id IS NOT NULL AND group_id IS NULL) OR (subject_id IS NULL AND group_id IS NOT NULL)",
            name="ck_role_bindings_subject_xor_group",
        ),
    )
    op.create_index("ix_role_bindings_tenant_subject", "role_bindings", ["tenant_id", "subject_id"])

    op.create_table(
        "api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subjects.id"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("key_prefix", sa.String(64), nullable=False),
        sa.Column("key_hash", sa.LargeBinary(), nullable=False),
        sa.Column("scopes", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("key_prefix", name="uq_api_keys_prefix"),
    )
    op.create_index("ix_api_keys_tenant_subject", "api_keys", ["tenant_id", "subject_id"])


def downgrade() -> None:
    op.drop_table("api_keys")
    op.drop_table("role_bindings")
    op.drop_table("group_members")
    op.drop_table("groups")
    op.drop_table("subjects")
    op.drop_table("tenants")
