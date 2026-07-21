"""# Eval schema — initial revision (LLD §2.16)

Revision ID: 0001_eval_initial
Revises:
Create Date: 2026-07-21
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_eval_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "eval_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("suite_version", sa.String(64), nullable=False),
        sa.Column("candidate_ref", sa.Text(), nullable=False),
        sa.Column(
            "baseline_scorecard_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_eval_jobs_tenant_created", "eval_jobs", ["tenant_id", "created_at"]
    )

    op.create_table(
        "scorecards",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("suite_version", sa.String(64), nullable=False),
        sa.Column("candidate_ref", sa.Text(), nullable=False),
        sa.Column("metrics", postgresql.JSONB(), nullable=False),
        sa.Column(
            "details",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_scorecards_tenant_kind",
        "scorecards",
        ["tenant_id", "kind", "suite_version"],
    )

    op.create_table(
        "gate_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("scorecard_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "baseline_scorecard_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("decision", sa.String(32), nullable=False),
        sa.Column(
            "reasons",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("gate_decisions")
    op.drop_index("ix_scorecards_tenant_kind", table_name="scorecards")
    op.drop_table("scorecards")
    op.drop_index("ix_eval_jobs_tenant_created", table_name="eval_jobs")
    op.drop_table("eval_jobs")
