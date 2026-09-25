"""Shared fixed-window rate limit counters.

The bucket holds 'global' or 'ip:' + a full SHA-256 HMAC (64 hex characters). The CHECK
constraint rejects every raw address form, including a bare IPv6 address, which is
exactly 32 hex characters and would have passed a shorter pattern.

Revision ID: 0007
Revises: 0006
"""

import sqlalchemy as sa
from alembic import op


revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rate_limit_counters",
        sa.Column("bucket", sa.Text(), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("hits", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("bucket", "window_start"),
        sa.CheckConstraint("hits > 0", name="rate_limit_counters_hits_positive"),
        sa.CheckConstraint(
            "bucket = 'global' OR bucket ~ '^ip:[0-9a-f]{64}$'",
            name="rate_limit_counters_bucket_opaque",
        ),
    )
    op.create_index("ix_rate_limit_counters_window_start", "rate_limit_counters", ["window_start"])


def downgrade() -> None:
    op.drop_index("ix_rate_limit_counters_window_start", table_name="rate_limit_counters")
    op.drop_table("rate_limit_counters")
