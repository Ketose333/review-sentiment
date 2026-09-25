"""ORM mapping for migrated PostgreSQL tables."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ModelRegistry(Base):
    __tablename__ = "model_registry"
    __table_args__ = (
        CheckConstraint("model_id IN ('tfidf_lr', 'lstm', 'klue_bert')", name="model_registry_id_allowed"),
        CheckConstraint("metrics ?& ARRAY['accuracy', 'precision', 'recall', 'f1'] AND jsonb_typeof(metrics) = 'object' AND jsonb_typeof(metrics->'accuracy') = 'number' AND jsonb_typeof(metrics->'precision') = 'number' AND jsonb_typeof(metrics->'recall') = 'number' AND jsonb_typeof(metrics->'f1') = 'number' AND (metrics->>'accuracy')::numeric BETWEEN 0 AND 1 AND (metrics->>'precision')::numeric BETWEEN 0 AND 1 AND (metrics->>'recall')::numeric BETWEEN 0 AND 1 AND (metrics->>'f1')::numeric BETWEEN 0 AND 1", name="model_registry_metrics_valid"),
        CheckConstraint("evaluation_scope ?& ARRAY['dataset', 'testSet', 'testCount', 'sampleSeed'] AND jsonb_typeof(evaluation_scope) = 'object' AND jsonb_typeof(evaluation_scope->'testCount') IN ('number', 'null') AND jsonb_typeof(evaluation_scope->'sampleSeed') IN ('number', 'null')", name="model_registry_evaluation_scope"),
    )

    model_id: Mapped[str] = mapped_column(Text, primary_key=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    artifact_repo: Mapped[str] = mapped_column(Text, nullable=False)
    artifact_revision: Mapped[str] = mapped_column(Text, nullable=False)
    artifact_manifest: Mapped[dict] = mapped_column(JSONB, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False)
    evaluation_scope: Mapped[dict] = mapped_column(JSONB, nullable=False)
    explanation_available: Mapped[bool] = mapped_column(Boolean, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    __table_args__ = (
        Index("ix_analysis_runs_expires_at", "expires_at"),
        CheckConstraint("status IN ('RECEIVED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'REJECTED')", name="analysis_runs_status_allowed"),
        CheckConstraint("label IS NULL OR label IN ('긍정', '부정')", name="analysis_runs_label_allowed"),
        CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 1)", name="analysis_runs_confidence_range"),
        CheckConstraint("duration_ms IS NULL OR duration_ms >= 0", name="analysis_runs_duration_nonnegative"),
        CheckConstraint("expires_at = created_at + interval '24 hours'", name="analysis_runs_ttl_24h"),
        CheckConstraint("(status = 'SUCCEEDED' AND label IS NOT NULL AND confidence IS NOT NULL AND error_code IS NULL AND completed_at IS NOT NULL) OR (status IN ('FAILED', 'REJECTED') AND label IS NULL AND confidence IS NULL AND error_code IS NOT NULL AND completed_at IS NOT NULL) OR (status IN ('RECEIVED', 'RUNNING') AND label IS NULL AND confidence IS NULL AND error_code IS NULL AND completed_at IS NULL)", name="analysis_runs_terminal_shape"),
    )

    analysis_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    model_id: Mapped[str] = mapped_column(Text, ForeignKey("model_registry.model_id"), nullable=False)
    model_version: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    label: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float)
    explanation_available: Mapped[bool] = mapped_column(Boolean, nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(Text)
    request_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RateLimitCounter(Base):
    """Shared fixed-window counters. `bucket` is 'global' or an opaque salted key."""

    __tablename__ = "rate_limit_counters"
    __table_args__ = (
        Index("ix_rate_limit_counters_window_start", "window_start"),
        CheckConstraint("hits > 0", name="rate_limit_counters_hits_positive"),
        CheckConstraint("bucket = 'global' OR bucket ~ '^ip:[0-9a-f]{64}$'", name="rate_limit_counters_bucket_opaque"),
    )

    bucket: Mapped[str] = mapped_column(Text, primary_key=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    hits: Mapped[int] = mapped_column(Integer, nullable=False)
