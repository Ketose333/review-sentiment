"""Create metadata-only analysis runs.

Revision ID: 0002
Revises: 0001
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analysis_runs",
        sa.Column("analysis_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("model_id", sa.Text(), sa.ForeignKey("model_registry.model_id"), nullable=False),
        sa.Column("model_version", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("label", sa.Text()),
        sa.Column("confidence", sa.Float()),
        sa.Column("explanation_available", sa.Boolean(), nullable=False),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("error_code", sa.Text()),
        sa.Column("request_id", UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('RECEIVED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'REJECTED')", name="analysis_runs_status_allowed"),
        sa.CheckConstraint("label IS NULL OR label IN ('긍정', '부정')", name="analysis_runs_label_allowed"),
        sa.CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 1)", name="analysis_runs_confidence_range"),
        sa.CheckConstraint("duration_ms IS NULL OR duration_ms >= 0", name="analysis_runs_duration_nonnegative"),
        sa.CheckConstraint("expires_at = created_at + interval '24 hours'", name="analysis_runs_ttl_24h"),
        sa.CheckConstraint("(status = 'SUCCEEDED' AND label IS NOT NULL AND confidence IS NOT NULL AND error_code IS NULL AND completed_at IS NOT NULL) OR (status IN ('FAILED', 'REJECTED') AND label IS NULL AND confidence IS NULL AND error_code IS NOT NULL AND completed_at IS NOT NULL) OR (status IN ('RECEIVED', 'RUNNING') AND label IS NULL AND confidence IS NULL AND error_code IS NULL AND completed_at IS NULL)", name="analysis_runs_terminal_shape"),
    )


def downgrade() -> None:
    op.drop_table("analysis_runs")
