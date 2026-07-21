"""Alembic migration script template."""

${imports}

revision = ${revid}
down_revision = ${down_revid}
branch_labels = ${branch_labels}
depends_on = ${depends_on}


def upgrade() -> None:
    ${upgrades}


def downgrade() -> None:
    ${downgrades}
