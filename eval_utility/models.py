"""EU-7 — SQLAlchemy 2.0 ORM models.

Supports both SQLite (tests/local) and Postgres (deploy) via the same models.
Re-keys annotation tables for multi-annotator coexistence per BACKEND_REWORK_BRIEF.md.

Tables:
  Existing (from store.py schema):
    - dataset, claim, claim_document_link, document_annotation
    - gold_span, claim_span_label, retrieval_judgment
    - forage_strategy, forage_query

  New (EU-7/8/9/10/11):
    - users, sessions, auth_tokens (EU-8)
    - capture_jobs (EU-10)
    - assignment_lease, claim_annotation_state (EU-9/11)
    - audit_log (cross-cutting)

Re-keying (EU-7):
  - retrieval_judgment PK: (claim_id, document_id, annotator_id)
  - claim_span_label PK: (claim_id, span_id, annotator_id)
  - gold_span: per-annotator by authorship (distinct span_id, each annotator_id)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _generate_id(prefix: str = "") -> str:
    """Generate a unique ID with optional prefix."""
    uid = uuid4().hex[:12]
    return f"{prefix}-{uid}" if prefix else uid


def _utcnow() -> datetime:
    """Current UTC timestamp."""
    return datetime.now(timezone.utc)


# Schema version for migrations
SCHEMA_VERSION = "gold_v1"


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


# -----------------------------------------------------------------------------
# Dataset (singleton)
# -----------------------------------------------------------------------------


class DatasetModel(Base):
    """Dataset metadata (singleton row)."""

    __tablename__ = "dataset"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    dataset_version: Mapped[str] = mapped_column(String(50), nullable=False, default="v1.0")
    schema_version: Mapped[str] = mapped_column(String(50), nullable=False)
    annotation_guidelines_version: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    __table_args__ = (CheckConstraint("id = 1", name="dataset_singleton"),)


# -----------------------------------------------------------------------------
# Users & Auth (EU-8)
# -----------------------------------------------------------------------------


class UserModel(Base):
    """User account."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: uuid4().hex)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="annotator")
    disabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    sessions: Mapped[list[SessionModel]] = relationship(back_populates="user", cascade="all, delete-orphan")

    __table_args__ = (CheckConstraint("role IN ('admin', 'annotator')", name="valid_role"),)


class SessionModel(Base):
    """User session (revocable)."""

    __tablename__ = "sessions"

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    csrf_token: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    user: Mapped[UserModel] = relationship(back_populates="sessions")

    __table_args__ = (Index("idx_sessions_user", "user_id"), Index("idx_sessions_expires", "expires_at"))


class AuthTokenModel(Base):
    """Auth tokens for invites and password resets."""

    __tablename__ = "auth_tokens"

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="annotator")
    purpose: Mapped[str] = mapped_column(String(20), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        CheckConstraint("purpose IN ('invite', 'password_reset')", name="valid_purpose"),
        Index("idx_auth_tokens_email", "email"),
    )


# -----------------------------------------------------------------------------
# Claims
# -----------------------------------------------------------------------------


class ClaimModel(Base):
    """A debate proposition."""

    __tablename__ = "claim"

    claim_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    family: Mapped[str | None] = mapped_column(String(20))
    proof_standard: Mapped[str | None] = mapped_column(String(10))
    split: Mapped[str] = mapped_column(String(10), default="train")
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    document_links: Mapped[list[ClaimDocumentLinkModel]] = relationship(back_populates="claim")
    annotation_state: Mapped[ClaimAnnotationStateModel | None] = relationship(back_populates="claim", uselist=False)

    __table_args__ = (
        CheckConstraint(
            "family IN ('policy', 'factual', 'comparative', 'predictive', 'causal', 'existence')", name="valid_family"
        ),
        CheckConstraint("proof_standard IN ('PE', 'CCE', 'BRD', 'DV')", name="valid_proof_standard"),
        CheckConstraint("split IN ('train', 'dev', 'test')", name="valid_split"),
    )


# -----------------------------------------------------------------------------
# Claim-Document Links
# -----------------------------------------------------------------------------


class ClaimDocumentLinkModel(Base):
    """Link between claim and document (gates T1/T3 eligibility)."""

    __tablename__ = "claim_document_link"

    claim_id: Mapped[str] = mapped_column(String(50), ForeignKey("claim.claim_id"), primary_key=True)
    document_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    origin: Mapped[str] = mapped_column(String(10), nullable=False)
    fixture_id: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    claim: Mapped[ClaimModel] = relationship(back_populates="document_links")

    __table_args__ = (CheckConstraint("origin IN ('search', 'manual')", name="valid_origin"),)


# -----------------------------------------------------------------------------
# Document Annotations
# -----------------------------------------------------------------------------


class DocumentAnnotationModel(Base):
    """Per-document annotation (claim-independent)."""

    __tablename__ = "document_annotation"

    document_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    fixture_id: Mapped[str] = mapped_column(String(100), nullable=False)
    exhaustively_annotated: Mapped[bool] = mapped_column(Boolean, default=False)
    lost_evidence_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    lost_evidence_note: Mapped[str | None] = mapped_column(Text)
    annotator_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
    # CC-2: MBFC Source Reliability metadata
    publisher_name: Mapped[str | None] = mapped_column(String(255))
    publisher_mbfc_key: Mapped[str | None] = mapped_column(String(100))
    mbfc_factual_rating: Mapped[str | None] = mapped_column(String(50))
    mbfc_bias_rating: Mapped[str | None] = mapped_column(String(50))
    source_reliability: Mapped[float | None] = mapped_column(Float)


# -----------------------------------------------------------------------------
# Gold Spans
# -----------------------------------------------------------------------------


class GoldSpanModel(Base):
    """Gold span (span-intrinsic, claim-independent, per-annotator by authorship)."""

    __tablename__ = "gold_span"

    span_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    document_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    fixture_id: Mapped[str] = mapped_column(String(100), nullable=False)
    char_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    char_length: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    is_claim_bearing: Mapped[bool | None] = mapped_column(Boolean)
    label_source: Mapped[str | None] = mapped_column(String(30))
    annotator_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
    # CC-2: Claim Attribution Metadata (captured from pipeline)
    claim_attribution: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    claimant_name: Mapped[str | None] = mapped_column(String(255))
    claimant_key: Mapped[str | None] = mapped_column(String(100))
    attribution_type: Mapped[str | None] = mapped_column(String(50))

    __table_args__ = (
        CheckConstraint(
            "label_source IN ('pipeline_prefill', 'pipeline_prefill_corrected', 'human_authored')",
            name="valid_label_source",
        ),
        Index("idx_gold_span_document", "document_id"),
        Index("idx_gold_span_annotator", "annotator_id"),
    )


# -----------------------------------------------------------------------------
# Claim-Span Labels (re-keyed for multi-annotator)
# -----------------------------------------------------------------------------


class ClaimSpanLabelModel(Base):
    """Claim-conditioned span label (germaneness + stance/strength).

    Re-keyed: PK is (claim_id, span_id, annotator_id) so multiple annotators
    can label the same (claim, span) pair.

    Note: annotator_id FK to users.id is intentionally not enforced to support
    backwards compat with 'system' annotator and tests without full auth setup.
    """

    __tablename__ = "claim_span_label"

    claim_id: Mapped[str] = mapped_column(String(50), ForeignKey("claim.claim_id"), primary_key=True)
    span_id: Mapped[str] = mapped_column(String(50), ForeignKey("gold_span.span_id"), primary_key=True)
    # No FK on annotator_id for backwards compat with 'system' annotator
    annotator_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    relevant_to_claim: Mapped[bool | None] = mapped_column(Boolean)
    stance: Mapped[str | None] = mapped_column(String(10))
    strength_ordinal: Mapped[str | None] = mapped_column(String(10))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        CheckConstraint("stance IN ('PRO', 'CON', 'NEUTRAL')", name="valid_stance"),
        CheckConstraint("strength_ordinal IN ('none', 'weak', 'moderate', 'strong')", name="valid_strength"),
        Index("idx_claim_span_label_claim", "claim_id"),
        Index("idx_claim_span_label_span", "span_id"),
    )


# -----------------------------------------------------------------------------
# Retrieval Judgments (re-keyed for multi-annotator)
# -----------------------------------------------------------------------------


class RetrievalJudgmentModel(Base):
    """T1 retrieval judgment (claim × document).

    Re-keyed: PK is (claim_id, document_id, annotator_id) so multiple annotators
    can judge the same (claim, document) pair.

    Note: annotator_id FK to users.id is intentionally not enforced to support
    backwards compat with 'system' annotator and tests without full auth setup.
    """

    __tablename__ = "retrieval_judgment"

    claim_id: Mapped[str] = mapped_column(String(50), ForeignKey("claim.claim_id"), primary_key=True)
    document_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    # No FK on annotator_id for backwards compat with 'system' annotator
    annotator_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    forage_query_id: Mapped[str | None] = mapped_column(String(50))
    relevant: Mapped[int | None] = mapped_column(Integer)
    retrieval_rank: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        Index("idx_retrieval_judgment_claim", "claim_id"),
        Index("idx_retrieval_judgment_document", "document_id"),
    )


# -----------------------------------------------------------------------------
# Fixture Metadata (CC-2)
# -----------------------------------------------------------------------------


class FixtureMetadataModel(Base):
    """Per-fixture metadata (search target, target metrics)."""

    __tablename__ = "fixture_metadata"

    fixture_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    search_target_preset: Mapped[str | None] = mapped_column(String(50))
    target_metrics: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


# -----------------------------------------------------------------------------
# Forage Strategies
# -----------------------------------------------------------------------------


class ForageStrategyModel(Base):
    """A forage strategy from db8r-mcts."""

    __tablename__ = "forage_strategy"

    forage_strategy_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    claim_id: Mapped[str | None] = mapped_column(String(50), ForeignKey("claim.claim_id"), index=True)
    claim_text: Mapped[str | None] = mapped_column(Text)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    perspective: Mapped[str | None] = mapped_column(String(30))
    generator_version: Mapped[str] = mapped_column(String(50), nullable=False)
    generator: Mapped[str | None] = mapped_column(String(50))
    claim_type: Mapped[str | None] = mapped_column(String(50))
    providers: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    context: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="mc5_endpoint")
    fallback_reason: Mapped[str | None] = mapped_column(Text)
    claim_decomposition: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    polarity_reversal: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    schema_plan: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        CheckConstraint("mode IN ('pregame', 'reactive')", name="valid_mode"),
        CheckConstraint("perspective IN ('supports_claim', 'contradicts_claim')", name="valid_perspective"),
        CheckConstraint("source IN ('mc5_endpoint', 'debate_trace')", name="valid_source"),
    )


# -----------------------------------------------------------------------------
# Forage Queries
# -----------------------------------------------------------------------------


class ForageQueryModel(Base):
    """A query from a forage strategy."""

    __tablename__ = "forage_query"

    forage_query_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    forage_strategy_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("forage_strategy.forage_strategy_id"), nullable=False, index=True
    )
    pool: Mapped[str] = mapped_column(String(10), nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    strategy: Mapped[str | None] = mapped_column(String(50))
    priority: Mapped[float | None] = mapped_column(Float)
    rank: Mapped[int | None] = mapped_column(Integer)
    providers: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    intent_label: Mapped[str | None] = mapped_column(String(100))
    rationale: Mapped[str | None] = mapped_column(Text)
    retrieval_role: Mapped[str | None] = mapped_column(String(50))
    scheme: Mapped[str | None] = mapped_column(String(100))
    critical_question_family: Mapped[str | None] = mapped_column(String(100))
    target_schema_need_id: Mapped[str | None] = mapped_column(String(50))
    fixture_id: Mapped[str | None] = mapped_column(String(100), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (CheckConstraint("pool IN ('PRO', 'CON')", name="valid_pool"),)


# Set up relationships after both classes are defined
ForageStrategyModel.queries = relationship(
    "ForageQueryModel", back_populates="forage_strategy_ref", cascade="all, delete-orphan"
)
ForageQueryModel.forage_strategy_ref = relationship("ForageStrategyModel", back_populates="queries")


# -----------------------------------------------------------------------------
# Assignment & Leasing (EU-9)
# -----------------------------------------------------------------------------


class AssignmentLeaseModel(Base):
    """Assignment and soft-lock lease for annotation units."""

    __tablename__ = "assignment_lease"

    unit_type: Mapped[str] = mapped_column(String(30), primary_key=True)
    unit_key: Mapped[str] = mapped_column(String(200), primary_key=True)
    annotator_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="assigned")
    leased_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        CheckConstraint("unit_type IN ('retrieval', 'span', 'label')", name="valid_unit_type"),
        CheckConstraint("status IN ('assigned', 'leased', 'completed')", name="valid_status"),
        Index("idx_assignment_lease_annotator", "annotator_id"),
    )


# -----------------------------------------------------------------------------
# Claim Annotation State (EU-11)
# -----------------------------------------------------------------------------


class ClaimAnnotationStateModel(Base):
    """Per-claim annotation state (retrieval_complete flag)."""

    __tablename__ = "claim_annotation_state"

    claim_id: Mapped[str] = mapped_column(String(50), ForeignKey("claim.claim_id"), primary_key=True)
    retrieval_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    claim: Mapped[ClaimModel] = relationship(back_populates="annotation_state")


# -----------------------------------------------------------------------------
# Capture Jobs (EU-10)
# -----------------------------------------------------------------------------


class CaptureJobModel(Base):
    """Capture job (async, stored in Postgres)."""

    __tablename__ = "capture_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: uuid4().hex)
    job_type: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    params: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("job_type IN ('search', 'extract', 'foraging')", name="valid_job_type"),
        CheckConstraint("status IN ('pending', 'running', 'completed', 'failed')", name="valid_job_status"),
        Index("idx_capture_jobs_status", "status"),
    )


# -----------------------------------------------------------------------------
# Audit Log (cross-cutting)
# -----------------------------------------------------------------------------


class AuditLogModel(Base):
    """Audit log for admin/security actions."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(50))
    target_id: Mapped[str | None] = mapped_column(String(100))
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    __table_args__ = (Index("idx_audit_log_user", "user_id"), Index("idx_audit_log_action", "action"))


# -----------------------------------------------------------------------------
# Evidence Quality Labels (Foraging Learning)
# -----------------------------------------------------------------------------


class DocumentQualityLabelModel(Base):
    """Document-level quality labels for foraging learning.

    These labels assess document quality independent of specific spans:
    - relevance: categorical relevance to claim
    - claim_relation: supports/contradicts/mixed/background
    - source_issues: paywall, attribution, staleness, etc.
    - corroboration: independent vs duplicate sources
    """

    __tablename__ = "document_quality_label"

    id: Mapped[str] = mapped_column(String(50), primary_key=True, default=lambda: _generate_id("dql"))
    document_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    claim_id: Mapped[str | None] = mapped_column(String(50), ForeignKey("claim.claim_id"), index=True)
    # Core relevance (categorical, extends numeric T1 scale)
    relevance: Mapped[str | None] = mapped_column(String(30))
    claim_relation: Mapped[str | None] = mapped_column(String(20))
    # Source issues (JSON array since can have multiple)
    source_issues: Mapped[list[str] | None] = mapped_column(JSON)
    # Corroboration tracking
    corroboration_status: Mapped[str | None] = mapped_column(String(20))
    corroboration_cluster_id: Mapped[str | None] = mapped_column(String(50), index=True)
    # Metadata
    annotator_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        CheckConstraint(
            "relevance IN ('germane', 'partially_germane', 'background', 'irrelevant')",
            name="valid_doc_relevance",
        ),
        CheckConstraint(
            "claim_relation IN ('supports', 'contradicts', 'mixed', 'background', 'unclear')",
            name="valid_claim_relation",
        ),
        CheckConstraint(
            "corroboration_status IN ('independent', 'same_cluster', 'duplicate')",
            name="valid_corroboration_status",
        ),
        Index("idx_doc_quality_document", "document_id"),
        Index("idx_doc_quality_claim", "claim_id"),
        Index("idx_doc_quality_cluster", "corroboration_cluster_id"),
    )


class SpanQualityLabelModel(Base):
    """Span-level quality labels for foraging learning.

    These labels assess extracted span quality:
    - extraction_quality: faithful/overbroad/underspecified/wrong/unsupported
    - grounding_quality: sufficient/missing_context/wrong_span/source_mismatch
    - evidence_usability: argument_support/rebuttal_support/context_only/unusable
    """

    __tablename__ = "span_quality_label"

    id: Mapped[str] = mapped_column(String(50), primary_key=True, default=lambda: _generate_id("sql"))
    span_id: Mapped[str] = mapped_column(String(50), ForeignKey("gold_span.span_id"), nullable=False, index=True)
    # Extraction quality
    extraction_quality: Mapped[str | None] = mapped_column(String(20))
    # Grounding quality
    grounding_quality: Mapped[str | None] = mapped_column(String(20))
    # Evidence usability
    evidence_usability: Mapped[str | None] = mapped_column(String(20))
    # Metadata
    annotator_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        CheckConstraint(
            "extraction_quality IN ('faithful', 'overbroad', 'underspecified', 'wrong', 'unsupported')",
            name="valid_extraction_quality",
        ),
        CheckConstraint(
            "grounding_quality IN ('sufficient', 'missing_context', 'wrong_span', 'source_mismatch')",
            name="valid_grounding_quality",
        ),
        CheckConstraint(
            "evidence_usability IN ('argument_support', 'rebuttal_support', 'context_only', 'unusable')",
            name="valid_evidence_usability",
        ),
        Index("idx_span_quality_span", "span_id"),
        Index("idx_span_quality_annotator", "annotator_id"),
    )
