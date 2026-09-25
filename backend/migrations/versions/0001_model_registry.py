"""Create model registry.

Revision ID: 0001
Revises:
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_registry",
        sa.Column("model_id", sa.Text(), primary_key=True),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("artifact_repo", sa.Text(), nullable=False),
        sa.Column("artifact_revision", sa.Text(), nullable=False),
        sa.Column("artifact_manifest", JSONB(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("metrics", JSONB(), nullable=False),
        sa.Column("evaluation_scope", JSONB(), nullable=False),
        sa.Column("explanation_available", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("model_id IN ('tfidf_lr', 'lstm', 'klue_bert')", name="model_registry_id_allowed"),
        sa.CheckConstraint("metrics ?& ARRAY['accuracy', 'precision', 'recall', 'f1'] AND jsonb_typeof(metrics) = 'object' AND jsonb_typeof(metrics->'accuracy') = 'number' AND jsonb_typeof(metrics->'precision') = 'number' AND jsonb_typeof(metrics->'recall') = 'number' AND jsonb_typeof(metrics->'f1') = 'number' AND (metrics->>'accuracy')::numeric BETWEEN 0 AND 1 AND (metrics->>'precision')::numeric BETWEEN 0 AND 1 AND (metrics->>'recall')::numeric BETWEEN 0 AND 1 AND (metrics->>'f1')::numeric BETWEEN 0 AND 1", name="model_registry_metrics_valid"),
        sa.CheckConstraint("evaluation_scope ?& ARRAY['dataset', 'testSet', 'testCount', 'sampleSeed'] AND jsonb_typeof(evaluation_scope) = 'object' AND jsonb_typeof(evaluation_scope->'testCount') IN ('number', 'null') AND jsonb_typeof(evaluation_scope->'sampleSeed') IN ('number', 'null')", name="model_registry_evaluation_scope"),
    )


def downgrade() -> None:
    op.drop_table("model_registry")
