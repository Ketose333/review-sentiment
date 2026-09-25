"""Register all required neural files and enable three-model explanation.

Revision ID: 0008
Revises: 0007
"""

from alembic import op
import json
import sqlalchemy as sa

MANIFESTS = {
    "lstm": {
        "models/lstm/model.h5": "aa87bac234a46daebda568a79000cb656dc781df39cbe28152200935a2f9f60b",
        "models/lstm/tokenizer.json": "ec62e121240daf19b5b206db0e91c4f108b740a7dd041173d5bfaa46c79da451",
    },
    "klue_bert": {
        "models/klue_bert/model.safetensors": "8a2e7480a194c64ffe0b22a35a3a0ecd9e4cc5cd5e68cb73436b399956f28423",
        "models/klue_bert/config.json": "a1a6b6ae0ce34fa89b53ddca458929c10c794f5394d68bbe727723f1fc8f94dd",
        "models/klue_bert/tokenizer.json": "f9d6539cd3f6972070d5531342d87ab67faa2bc7d0570fe454715031e893191a",
        "models/klue_bert/tokenizer_config.json": "3cfbb173107c0d1668eb08657cddba58563c9daa94f7229006d08c40e5e75bb3",
    },
}
PREVIOUS_MANIFESTS = {
    "lstm": {"models/lstm/model.h5": "aa87bac234a46daebda568a79000cb656dc781df39cbe28152200935a2f9f60b"},
    "klue_bert": {"models/klue_bert/model.safetensors": "8a2e7480a194c64ffe0b22a35a3a0ecd9e4cc5cd5e68cb73436b399956f28423"},
}

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for model_id in ("lstm", "klue_bert"):
        op.get_bind().execute(
            sa.text("UPDATE model_registry SET artifact_manifest = CAST(:manifest AS jsonb), enabled = true, explanation_available = true, updated_at = now() WHERE model_id = :model_id"),
            {"model_id": model_id, "manifest": json.dumps(MANIFESTS[model_id])},
        )


def downgrade() -> None:
    for model_id in ("lstm", "klue_bert"):
        op.get_bind().execute(
            sa.text("UPDATE model_registry SET artifact_manifest = CAST(:manifest AS jsonb), enabled = false, explanation_available = false, updated_at = now() WHERE model_id = :model_id"),
            {"model_id": model_id, "manifest": json.dumps(PREVIOUS_MANIFESTS[model_id])},
        )
