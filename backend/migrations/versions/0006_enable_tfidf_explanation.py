"""Advertise TF-IDF LIME support.

Revision ID: 0006
Revises: 0005
"""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE model_registry SET explanation_available = true, updated_at = now() WHERE model_id = 'tfidf_lr'")


def downgrade() -> None:
    op.execute("UPDATE model_registry SET explanation_available = false, updated_at = now() WHERE model_id = 'tfidf_lr'")
