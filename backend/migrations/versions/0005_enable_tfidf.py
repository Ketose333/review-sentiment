"""Enable the verified TF-IDF inference route.

Revision ID: 0005
Revises: 0004
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE model_registry SET enabled = true, updated_at = now() WHERE model_id = 'tfidf_lr'")


def downgrade() -> None:
    op.execute("UPDATE model_registry SET enabled = false, updated_at = now() WHERE model_id = 'tfidf_lr'")
