"""# Index meta schema — initial revision (LLD §4.7)

Revision ID: 0001_index_meta_initial
Revises:
Create Date: 2026-07-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_index_meta_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "index_generations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("repository_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("commit_sha", sa.String(40), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("embedding_model", sa.Text(), nullable=False),
        sa.Column("embedding_dim", sa.Integer(), nullable=False),
        sa.Column("vector_namespace", sa.Text(), nullable=False),
        sa.Column("lexical_index_name", sa.Text(), nullable=False),
        sa.Column("stats", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_index_generations_repo_state",
        "index_generations",
        ["repository_id", "state"],
    )
    op.create_index(
        "ix_index_generations_tenant_created",
        "index_generations",
        ["tenant_id", "created_at"],
    )
    # Partial unique: one active generation per repository (LLD §4.7)
    op.execute(
        """
        CREATE UNIQUE INDEX uq_index_generations_active_repo
        ON index_generations (repository_id)
        WHERE state = 'active'
        """
    )

    op.create_table(
        "symbol_nodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("repository_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "generation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("index_generations.id"),
            nullable=False,
        ),
        sa.Column("language", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("qualified_name", sa.Text(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("start_line", sa.Integer(), nullable=False),
        sa.Column("end_line", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
    )
    op.create_index(
        "ix_symbol_nodes_generation_qname",
        "symbol_nodes",
        ["generation_id", "qualified_name"],
    )
    op.create_index(
        "ix_symbol_nodes_generation_path",
        "symbol_nodes",
        ["generation_id", "path"],
    )
    op.create_index(
        "ix_symbol_nodes_repository_name",
        "symbol_nodes",
        ["repository_id", "name"],
    )

    op.create_table(
        "symbol_edges",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "generation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("index_generations.id"),
            nullable=False,
        ),
        sa.Column(
            "src_symbol_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("symbol_nodes.id"),
            nullable=False,
        ),
        sa.Column(
            "dst_symbol_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("symbol_nodes.id"),
            nullable=False,
        ),
        sa.Column("edge_type", sa.Text(), nullable=False),
    )
    op.create_index(
        "ix_symbol_edges_src",
        "symbol_edges",
        ["generation_id", "src_symbol_id", "edge_type"],
    )
    op.create_index(
        "ix_symbol_edges_dst",
        "symbol_edges",
        ["generation_id", "dst_symbol_id", "edge_type"],
    )

    op.create_table(
        "dependency_packages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "generation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("index_generations.id"),
            nullable=False,
        ),
        sa.Column("ecosystem", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
    )
    op.create_index(
        "ix_dependency_packages_gen_eco_name",
        "dependency_packages",
        ["generation_id", "ecosystem", "name"],
    )


def downgrade() -> None:
    op.drop_table("dependency_packages")
    op.drop_table("symbol_edges")
    op.drop_table("symbol_nodes")
    op.execute("DROP INDEX IF EXISTS uq_index_generations_active_repo")
    op.drop_table("index_generations")
