"""Register verified deployment artifacts and evaluation scope.

Revision ID: 0004
Revises: 0003
"""

from datetime import datetime, timezone
import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

REPO = "Ketose333/review-sentiment-assets"
REVISION = "915d7784e3c81333d6812913b0a80eda37fdbd41"


def upgrade() -> None:
    registry = sa.table(
        "model_registry",
        sa.column("model_id", sa.Text()),
        sa.column("display_name", sa.Text()),
        sa.column("artifact_repo", sa.Text()),
        sa.column("artifact_revision", sa.Text()),
        sa.column("artifact_manifest", JSONB()),
        sa.column("enabled", sa.Boolean()),
        sa.column("metrics", JSONB()),
        sa.column("evaluation_scope", JSONB()),
        sa.column("explanation_available", sa.Boolean()),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    now = datetime.now(timezone.utc)
    common = {
        "artifact_repo": REPO,
        "artifact_revision": REVISION,
        "enabled": False,  # Stage A has no inference route.
        "explanation_available": False,
        "updated_at": now,
    }
    op.bulk_insert(
        registry,
        [
            {
                **common,
                "model_id": "tfidf_lr",
                "display_name": "TF-IDF + LogisticRegression",
                "artifact_manifest": op.inline_literal(json.dumps({
                    "models/tfidf_lr/model.pkl": "8eb8571babaf37d452b3b894281fde6997c6b2aaf8533efdfb85aa6f28bbe611",
                    "models/tfidf_lr/vectorizer.pkl": "69df406990335fa9ba1e2d1411ad2a56a41ecba40abded1781cafff404727118",
                })),
                "metrics": op.inline_literal(json.dumps({"accuracy": 0.837, "precision": 0.8463, "recall": 0.8263, "f1": 0.8362})),
                "evaluation_scope": op.inline_literal(json.dumps({"dataset": "NSMC", "testSet": "ratings_test.txt (dropna document)", "testCount": None, "sampleSeed": None})),
            },
            {
                **common,
                "model_id": "lstm",
                "display_name": "LSTM",
                "artifact_manifest": op.inline_literal(json.dumps({"models/lstm/model.h5": "aa87bac234a46daebda568a79000cb656dc781df39cbe28152200935a2f9f60b"})),
                "metrics": op.inline_literal(json.dumps({"accuracy": 0.8238, "precision": 0.871, "recall": 0.7631, "f1": 0.8135})),
                "evaluation_scope": op.inline_literal(json.dumps({"dataset": "NSMC", "testSet": "ratings_test.txt (dropna document)", "testCount": None, "sampleSeed": None})),
            },
            {
                **common,
                "model_id": "klue_bert",
                "display_name": "KLUE-BERT",
                "artifact_manifest": op.inline_literal(json.dumps({"models/klue_bert/model.safetensors": "8a2e7480a194c64ffe0b22a35a3a0ecd9e4cc5cd5e68cb73436b399956f28423"})),
                "metrics": op.inline_literal(json.dumps({"accuracy": 0.878, "precision": 0.8539, "recall": 0.9102, "f1": 0.8811})),
                "evaluation_scope": op.inline_literal(json.dumps({"dataset": "NSMC", "testSet": "ratings_test.txt (dropna document), sampled", "testCount": 5000, "sampleSeed": 42})),
            },
        ],
        multiinsert=False,
    )


def downgrade() -> None:
    op.execute("DELETE FROM model_registry WHERE model_id IN ('tfidf_lr', 'lstm', 'klue_bert')")
