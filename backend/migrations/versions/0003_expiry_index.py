"""Index analysis expiry for periodic pruning.

Revision ID: 0003
Revises: 0002
"""

from alembic import op


revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_analysis_runs_expires_at", "analysis_runs", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_analysis_runs_expires_at", table_name="analysis_runs")
