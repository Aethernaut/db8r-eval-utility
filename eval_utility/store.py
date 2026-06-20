"""EU-7 — Gold store (SQLAlchemy 2.0).

Implements the design-note §4 schema with SQLAlchemy ORM for SQLite (tests/local)
and Postgres (deploy) support via the same models.

Record types (see docs/gold-eval-design.md §4):
  - claim                (id, text, family, proof_standard, split)
  - claim_document_link  (claim_id, document_id, origin=search|manual)
  - document_annotation  (document_id, fixture_id, exhaustively_annotated, lost_evidence_flag)
  - gold_span            (span_id, document_id, offsets, text, is_claim_bearing, label_source, ...)
  - claim_span_label     (claim_id, span_id, annotator_id, relevant_to_claim, [stance, strength])
  - retrieval_judgment   (claim_id, document_id, annotator_id, forage_query_id, relevant, retrieval_rank)
  - forage_strategy      (forage_strategy_id, claim_id, mode, generator_version, source)
  - forage_query         (forage_query_id, forage_strategy_id, pool, query, fixture_id, ...)
  - dataset              (dataset_version, schema_version, annotation_guidelines_version)

Re-keyed for multi-annotator (EU-7):
  - retrieval_judgment PK: (claim_id, document_id, annotator_id)
  - claim_span_label PK: (claim_id, span_id, annotator_id)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import Settings, get_settings
from .database import init_db, session_scope
from .models import (
    SCHEMA_VERSION,
    ClaimDocumentLinkModel,
    ClaimModel,
    ClaimSpanLabelModel,
    DatasetModel,
    DocumentAnnotationModel,
    ForageQueryModel,
    ForageStrategyModel,
    GoldSpanModel,
    RetrievalJudgmentModel,
)

# Re-export SCHEMA_VERSION
__all__ = ["SCHEMA_VERSION", "GoldStore"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _generate_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


# --- Dataclasses for records (public API, unchanged from original) ---


@dataclass
class Claim:
    """A debate proposition."""

    claim_id: str
    text: str
    family: str | None = None  # policy|factual|comparative|predictive|causal|existence
    proof_standard: str | None = None  # PE|CCE|BRD|DV
    split: str = "train"  # train|dev|test
    notes: str | None = None
    created_at: str = ""
    updated_at: str = ""


@dataclass
class ClaimDocumentLink:
    """Link between claim and document (gates T1/T3 eligibility)."""

    claim_id: str
    document_id: str  # content-addressed by source_text_hash
    origin: str  # search|manual
    fixture_id: str | None = None
    notes: str | None = None
    created_at: str = ""


@dataclass
class DocumentAnnotation:
    """Per-document annotation (claim-independent)."""

    document_id: str  # content-addressed by source_text_hash
    fixture_id: str
    exhaustively_annotated: bool = False
    lost_evidence_flag: bool = False
    lost_evidence_note: str | None = None
    annotator_id: str | None = None
    created_at: str = ""
    updated_at: str = ""


@dataclass
class GoldSpan:
    """A gold span (span-intrinsic, claim-independent)."""

    span_id: str
    document_id: str  # content-addressed by source_text_hash
    fixture_id: str
    char_offset: int
    char_length: int
    text: str  # verbatim copy
    is_claim_bearing: bool | None = None
    label_source: str | None = None  # pipeline_prefill|pipeline_prefill_corrected|human_authored
    annotator_id: str | None = None
    notes: str | None = None
    created_at: str = ""
    updated_at: str = ""


@dataclass
class ClaimSpanLabel:
    """Claim-conditioned span label (germaneness + stance/strength)."""

    claim_id: str
    span_id: str
    relevant_to_claim: bool | None = None
    stance: str | None = None  # PRO|CON|NEUTRAL (v2)
    strength_ordinal: str | None = None  # none|weak|moderate|strong (v2)
    annotator_id: str | None = None
    notes: str | None = None
    created_at: str = ""
    updated_at: str = ""


@dataclass
class RetrievalJudgment:
    """T1 retrieval judgment (claim × document)."""

    claim_id: str
    document_id: str  # content-addressed by source_text_hash
    forage_query_id: str | None = None
    relevant: int | None = None  # bool or graded 0-3
    retrieval_rank: int | None = None
    annotator_id: str | None = None
    notes: str | None = None
    created_at: str = ""
    updated_at: str = ""


@dataclass
class ForageStrategyRecord:
    """A forage strategy from db8r-mcts."""

    forage_strategy_id: str
    claim_id: str | None
    claim_text: str | None
    mode: str  # pregame|reactive
    perspective: str | None  # supports_claim|contradicts_claim
    generator_version: str
    generator: str | None = None
    claim_type: str | None = None
    providers: list[str] = field(default_factory=list)
    context: dict[str, Any] | None = None  # reactive only
    source: str = "mc5_endpoint"  # mc5_endpoint|debate_trace
    fallback_reason: str | None = None
    claim_decomposition: dict[str, Any] | None = None
    polarity_reversal: dict[str, Any] | None = None
    schema_plan: dict[str, Any] | None = None
    captured_at: str = ""
    created_at: str = ""


@dataclass
class ForageQueryRecord:
    """A query from a forage strategy."""

    forage_query_id: str
    forage_strategy_id: str
    pool: str  # PRO|CON
    query: str
    strategy: str | None = None
    priority: float | None = None
    rank: int | None = None
    providers: list[str] = field(default_factory=list)
    intent_label: str | None = None
    rationale: str | None = None
    retrieval_role: str | None = None
    scheme: str | None = None
    critical_question_family: str | None = None
    target_schema_need_id: str | None = None
    fixture_id: str | None = None
    created_at: str = ""


@dataclass
class Dataset:
    """Dataset metadata (singleton)."""

    dataset_version: str
    schema_version: str
    annotation_guidelines_version: str | None = None
    created_at: str = ""
    updated_at: str = ""


# --- Conversion helpers ---


def _claim_from_model(model: ClaimModel) -> Claim:
    return Claim(
        claim_id=model.claim_id,
        text=model.text,
        family=model.family,
        proof_standard=model.proof_standard,
        split=model.split,
        notes=model.notes,
        created_at=model.created_at.isoformat() if model.created_at else "",
        updated_at=model.updated_at.isoformat() if model.updated_at else "",
    )


def _claim_document_link_from_model(model: ClaimDocumentLinkModel) -> ClaimDocumentLink:
    return ClaimDocumentLink(
        claim_id=model.claim_id,
        document_id=model.document_id,
        origin=model.origin,
        fixture_id=model.fixture_id,
        notes=model.notes,
        created_at=model.created_at.isoformat() if model.created_at else "",
    )


def _document_annotation_from_model(model: DocumentAnnotationModel) -> DocumentAnnotation:
    return DocumentAnnotation(
        document_id=model.document_id,
        fixture_id=model.fixture_id,
        exhaustively_annotated=model.exhaustively_annotated,
        lost_evidence_flag=model.lost_evidence_flag,
        lost_evidence_note=model.lost_evidence_note,
        annotator_id=model.annotator_id,
        created_at=model.created_at.isoformat() if model.created_at else "",
        updated_at=model.updated_at.isoformat() if model.updated_at else "",
    )


def _gold_span_from_model(model: GoldSpanModel) -> GoldSpan:
    return GoldSpan(
        span_id=model.span_id,
        document_id=model.document_id,
        fixture_id=model.fixture_id,
        char_offset=model.char_offset,
        char_length=model.char_length,
        text=model.text,
        is_claim_bearing=model.is_claim_bearing,
        label_source=model.label_source,
        annotator_id=model.annotator_id,
        notes=model.notes,
        created_at=model.created_at.isoformat() if model.created_at else "",
        updated_at=model.updated_at.isoformat() if model.updated_at else "",
    )


def _claim_span_label_from_model(model: ClaimSpanLabelModel) -> ClaimSpanLabel:
    return ClaimSpanLabel(
        claim_id=model.claim_id,
        span_id=model.span_id,
        relevant_to_claim=model.relevant_to_claim,
        stance=model.stance,
        strength_ordinal=model.strength_ordinal,
        annotator_id=model.annotator_id,
        notes=model.notes,
        created_at=model.created_at.isoformat() if model.created_at else "",
        updated_at=model.updated_at.isoformat() if model.updated_at else "",
    )


def _retrieval_judgment_from_model(model: RetrievalJudgmentModel) -> RetrievalJudgment:
    return RetrievalJudgment(
        claim_id=model.claim_id,
        document_id=model.document_id,
        forage_query_id=model.forage_query_id,
        relevant=model.relevant,
        retrieval_rank=model.retrieval_rank,
        annotator_id=model.annotator_id,
        notes=model.notes,
        created_at=model.created_at.isoformat() if model.created_at else "",
        updated_at=model.updated_at.isoformat() if model.updated_at else "",
    )


def _forage_strategy_from_model(model: ForageStrategyModel) -> ForageStrategyRecord:
    providers = model.providers if isinstance(model.providers, list) else []
    return ForageStrategyRecord(
        forage_strategy_id=model.forage_strategy_id,
        claim_id=model.claim_id,
        claim_text=model.claim_text,
        mode=model.mode,
        perspective=model.perspective,
        generator_version=model.generator_version,
        generator=model.generator,
        claim_type=model.claim_type,
        providers=providers,
        context=model.context,
        source=model.source,
        fallback_reason=model.fallback_reason,
        claim_decomposition=model.claim_decomposition,
        polarity_reversal=model.polarity_reversal,
        schema_plan=model.schema_plan,
        captured_at=model.captured_at.isoformat() if model.captured_at else "",
        created_at=model.created_at.isoformat() if model.created_at else "",
    )


def _forage_query_from_model(model: ForageQueryModel) -> ForageQueryRecord:
    providers = model.providers if isinstance(model.providers, list) else []
    return ForageQueryRecord(
        forage_query_id=model.forage_query_id,
        forage_strategy_id=model.forage_strategy_id,
        pool=model.pool,
        query=model.query,
        strategy=model.strategy,
        priority=model.priority,
        rank=model.rank,
        providers=providers,
        intent_label=model.intent_label,
        rationale=model.rationale,
        retrieval_role=model.retrieval_role,
        scheme=model.scheme,
        critical_question_family=model.critical_question_family,
        target_schema_need_id=model.target_schema_need_id,
        fixture_id=model.fixture_id,
        created_at=model.created_at.isoformat() if model.created_at else "",
    )


def _dataset_from_model(model: DatasetModel) -> Dataset:
    return Dataset(
        dataset_version=model.dataset_version,
        schema_version=model.schema_version,
        annotation_guidelines_version=model.annotation_guidelines_version,
        created_at=model.created_at.isoformat() if model.created_at else "",
        updated_at=model.updated_at.isoformat() if model.updated_at else "",
    )


# --- Store class ---


class GoldStore:
    """SQLAlchemy-backed store for gold annotations.

    Supports SQLite (tests/local) and Postgres (deploy) via DATABASE_URL.
    """

    def __init__(
        self,
        db_path: str | Path | None = None,
        settings: Settings | None = None,
        session: Session | None = None,
    ) -> None:
        """Initialize the store.

        Args:
            db_path: Legacy SQLite path (for backwards compat). Ignored if session provided.
            settings: Optional settings override.
            session: Optional SQLAlchemy session for dependency injection.
        """
        self.settings = settings or get_settings()
        self._external_session = session

        # If db_path provided, override DATABASE_URL temporarily (backwards compat for tests)
        if db_path is not None and session is None:
            # For backwards compat, allow passing a db_path to create a SQLite store
            self._db_path = Path(db_path)
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            # Override settings with SQLite URL
            import os

            os.environ["EVAL_DATABASE_URL"] = f"sqlite:///{self._db_path}"
            from .database import reset_engine

            reset_engine()

        # Initialize schema
        if session is None:
            init_db()
            self._ensure_dataset_singleton()

    def _ensure_dataset_singleton(self) -> None:
        """Ensure the dataset singleton row exists."""
        with session_scope() as session:
            existing = session.execute(select(DatasetModel)).scalar_one_or_none()
            if existing is None:
                dataset = DatasetModel(
                    id=1,
                    dataset_version="v1.0",
                    schema_version=SCHEMA_VERSION,
                )
                session.add(dataset)

    def _get_session(self):
        """Get a session - either external or create a new scope."""
        if self._external_session is not None:
            return self._external_session
        return session_scope()

    # --- Claim methods ---

    def upsert_claim(self, claim: Claim) -> Claim:
        """Insert or update a claim."""
        with session_scope() as session:
            existing = session.execute(select(ClaimModel).where(ClaimModel.claim_id == claim.claim_id)).scalar_one_or_none()

            if existing:
                existing.text = claim.text
                existing.family = claim.family
                existing.proof_standard = claim.proof_standard
                existing.split = claim.split
                existing.notes = claim.notes
                model = existing
            else:
                model = ClaimModel(
                    claim_id=claim.claim_id,
                    text=claim.text,
                    family=claim.family,
                    proof_standard=claim.proof_standard,
                    split=claim.split,
                    notes=claim.notes,
                )
                session.add(model)

            session.flush()
            return _claim_from_model(model)

    def get_claim(self, claim_id: str) -> Claim | None:
        """Get a claim by ID."""
        with session_scope() as session:
            model = session.execute(select(ClaimModel).where(ClaimModel.claim_id == claim_id)).scalar_one_or_none()
            if model:
                return _claim_from_model(model)
        return None

    def list_claims(self, split: str | None = None, family: str | None = None) -> list[Claim]:
        """List claims, optionally filtered by split and/or family."""
        with session_scope() as session:
            stmt = select(ClaimModel)
            if split:
                stmt = stmt.where(ClaimModel.split == split)
            if family:
                stmt = stmt.where(ClaimModel.family == family)
            stmt = stmt.order_by(ClaimModel.claim_id)
            models = session.execute(stmt).scalars().all()
            return [_claim_from_model(m) for m in models]

    def delete_claim(self, claim_id: str) -> bool:
        """Delete a claim by ID."""
        with session_scope() as session:
            model = session.execute(select(ClaimModel).where(ClaimModel.claim_id == claim_id)).scalar_one_or_none()
            if model:
                session.delete(model)
                return True
        return False

    # --- Claim-Document Link methods ---

    def upsert_claim_document_link(self, link: ClaimDocumentLink) -> ClaimDocumentLink:
        """Insert or update a claim-document link."""
        with session_scope() as session:
            existing = session.execute(
                select(ClaimDocumentLinkModel).where(
                    ClaimDocumentLinkModel.claim_id == link.claim_id,
                    ClaimDocumentLinkModel.document_id == link.document_id,
                )
            ).scalar_one_or_none()

            if existing:
                existing.origin = link.origin
                existing.fixture_id = link.fixture_id
                existing.notes = link.notes
                model = existing
            else:
                model = ClaimDocumentLinkModel(
                    claim_id=link.claim_id,
                    document_id=link.document_id,
                    origin=link.origin,
                    fixture_id=link.fixture_id,
                    notes=link.notes,
                )
                session.add(model)

            session.flush()
            return _claim_document_link_from_model(model)

    def get_documents_for_claim(self, claim_id: str) -> list[ClaimDocumentLink]:
        """Get all document links for a claim."""
        with session_scope() as session:
            stmt = (
                select(ClaimDocumentLinkModel)
                .where(ClaimDocumentLinkModel.claim_id == claim_id)
                .order_by(ClaimDocumentLinkModel.created_at)
            )
            models = session.execute(stmt).scalars().all()
            return [_claim_document_link_from_model(m) for m in models]

    def delete_claim_document_link(self, claim_id: str, document_id: str) -> bool:
        """Delete a claim-document link."""
        with session_scope() as session:
            model = session.execute(
                select(ClaimDocumentLinkModel).where(
                    ClaimDocumentLinkModel.claim_id == claim_id,
                    ClaimDocumentLinkModel.document_id == document_id,
                )
            ).scalar_one_or_none()
            if model:
                session.delete(model)
                return True
        return False

    # --- Document Annotation methods ---

    def upsert_document_annotation(self, annotation: DocumentAnnotation) -> DocumentAnnotation:
        """Insert or update a document annotation."""
        with session_scope() as session:
            existing = session.execute(
                select(DocumentAnnotationModel).where(DocumentAnnotationModel.document_id == annotation.document_id)
            ).scalar_one_or_none()

            if existing:
                existing.exhaustively_annotated = annotation.exhaustively_annotated
                existing.lost_evidence_flag = annotation.lost_evidence_flag
                existing.lost_evidence_note = annotation.lost_evidence_note
                existing.annotator_id = annotation.annotator_id
                model = existing
            else:
                model = DocumentAnnotationModel(
                    document_id=annotation.document_id,
                    fixture_id=annotation.fixture_id,
                    exhaustively_annotated=annotation.exhaustively_annotated,
                    lost_evidence_flag=annotation.lost_evidence_flag,
                    lost_evidence_note=annotation.lost_evidence_note,
                    annotator_id=annotation.annotator_id,
                )
                session.add(model)

            session.flush()
            return _document_annotation_from_model(model)

    def get_document_annotation(self, document_id: str) -> DocumentAnnotation | None:
        """Get annotation for a document."""
        with session_scope() as session:
            model = session.execute(
                select(DocumentAnnotationModel).where(DocumentAnnotationModel.document_id == document_id)
            ).scalar_one_or_none()
            if model:
                return _document_annotation_from_model(model)
        return None

    # --- Gold Span methods ---

    def upsert_gold_span(self, span: GoldSpan) -> GoldSpan:
        """Insert or update a gold span."""
        with session_scope() as session:
            existing = session.execute(
                select(GoldSpanModel).where(GoldSpanModel.span_id == span.span_id)
            ).scalar_one_or_none()

            if existing:
                existing.is_claim_bearing = span.is_claim_bearing
                existing.label_source = span.label_source
                existing.annotator_id = span.annotator_id
                existing.notes = span.notes
                model = existing
            else:
                model = GoldSpanModel(
                    span_id=span.span_id,
                    document_id=span.document_id,
                    fixture_id=span.fixture_id,
                    char_offset=span.char_offset,
                    char_length=span.char_length,
                    text=span.text,
                    is_claim_bearing=span.is_claim_bearing,
                    label_source=span.label_source,
                    annotator_id=span.annotator_id,
                    notes=span.notes,
                )
                session.add(model)

            session.flush()
            return _gold_span_from_model(model)

    def get_gold_span(self, span_id: str) -> GoldSpan | None:
        """Get a gold span by ID."""
        with session_scope() as session:
            model = session.execute(select(GoldSpanModel).where(GoldSpanModel.span_id == span_id)).scalar_one_or_none()
            if model:
                return _gold_span_from_model(model)
        return None

    def get_spans_for_document(self, document_id: str) -> list[GoldSpan]:
        """Get all gold spans for a document."""
        with session_scope() as session:
            stmt = (
                select(GoldSpanModel)
                .where(GoldSpanModel.document_id == document_id)
                .order_by(GoldSpanModel.char_offset)
            )
            models = session.execute(stmt).scalars().all()
            return [_gold_span_from_model(m) for m in models]

    def list_spans(
        self,
        document_id: str | None = None,
        is_claim_bearing: bool | None = None,
        label_source: str | None = None,
    ) -> list[GoldSpan]:
        """List spans with optional filters."""
        with session_scope() as session:
            stmt = select(GoldSpanModel)
            if document_id:
                stmt = stmt.where(GoldSpanModel.document_id == document_id)
            if is_claim_bearing is not None:
                stmt = stmt.where(GoldSpanModel.is_claim_bearing == is_claim_bearing)
            if label_source:
                stmt = stmt.where(GoldSpanModel.label_source == label_source)
            stmt = stmt.order_by(GoldSpanModel.char_offset)
            models = session.execute(stmt).scalars().all()
            return [_gold_span_from_model(m) for m in models]

    def delete_gold_span(self, span_id: str) -> bool:
        """Delete a gold span by ID."""
        with session_scope() as session:
            model = session.execute(select(GoldSpanModel).where(GoldSpanModel.span_id == span_id)).scalar_one_or_none()
            if model:
                session.delete(model)
                return True
        return False

    # --- Claim-Span Label methods ---

    def upsert_claim_span_label(self, label: ClaimSpanLabel) -> ClaimSpanLabel:
        """Insert or update a claim-span label.

        Note: With multi-annotator support, the PK is (claim_id, span_id, annotator_id).
        For backwards compat, annotator_id defaults to 'system' if not provided.
        """
        annotator_id = label.annotator_id or "system"

        with session_scope() as session:
            existing = session.execute(
                select(ClaimSpanLabelModel).where(
                    ClaimSpanLabelModel.claim_id == label.claim_id,
                    ClaimSpanLabelModel.span_id == label.span_id,
                    ClaimSpanLabelModel.annotator_id == annotator_id,
                )
            ).scalar_one_or_none()

            if existing:
                existing.relevant_to_claim = label.relevant_to_claim
                existing.stance = label.stance
                existing.strength_ordinal = label.strength_ordinal
                existing.notes = label.notes
                model = existing
            else:
                model = ClaimSpanLabelModel(
                    claim_id=label.claim_id,
                    span_id=label.span_id,
                    annotator_id=annotator_id,
                    relevant_to_claim=label.relevant_to_claim,
                    stance=label.stance,
                    strength_ordinal=label.strength_ordinal,
                    notes=label.notes,
                )
                session.add(model)

            session.flush()
            return _claim_span_label_from_model(model)

    def get_labels_for_span(self, span_id: str) -> list[ClaimSpanLabel]:
        """Get all claim labels for a span."""
        with session_scope() as session:
            stmt = select(ClaimSpanLabelModel).where(ClaimSpanLabelModel.span_id == span_id)
            models = session.execute(stmt).scalars().all()
            return [_claim_span_label_from_model(m) for m in models]

    def get_labels_for_claim(self, claim_id: str) -> list[ClaimSpanLabel]:
        """Get all span labels for a claim."""
        with session_scope() as session:
            stmt = select(ClaimSpanLabelModel).where(ClaimSpanLabelModel.claim_id == claim_id)
            models = session.execute(stmt).scalars().all()
            return [_claim_span_label_from_model(m) for m in models]

    def get_label(self, claim_id: str, span_id: str, annotator_id: str | None = None) -> ClaimSpanLabel | None:
        """Get a specific claim-span label."""
        annotator_id = annotator_id or "system"
        with session_scope() as session:
            model = session.execute(
                select(ClaimSpanLabelModel).where(
                    ClaimSpanLabelModel.claim_id == claim_id,
                    ClaimSpanLabelModel.span_id == span_id,
                    ClaimSpanLabelModel.annotator_id == annotator_id,
                )
            ).scalar_one_or_none()
            if model:
                return _claim_span_label_from_model(model)
        return None

    def delete_claim_span_label(self, claim_id: str, span_id: str, annotator_id: str | None = None) -> bool:
        """Delete a claim-span label."""
        annotator_id = annotator_id or "system"
        with session_scope() as session:
            model = session.execute(
                select(ClaimSpanLabelModel).where(
                    ClaimSpanLabelModel.claim_id == claim_id,
                    ClaimSpanLabelModel.span_id == span_id,
                    ClaimSpanLabelModel.annotator_id == annotator_id,
                )
            ).scalar_one_or_none()
            if model:
                session.delete(model)
                return True
        return False

    # --- Retrieval Judgment methods ---

    def upsert_retrieval_judgment(self, judgment: RetrievalJudgment) -> RetrievalJudgment:
        """Insert or update a retrieval judgment.

        Note: With multi-annotator support, the PK is (claim_id, document_id, annotator_id).
        For backwards compat, annotator_id defaults to 'system' if not provided.
        """
        annotator_id = judgment.annotator_id or "system"

        with session_scope() as session:
            existing = session.execute(
                select(RetrievalJudgmentModel).where(
                    RetrievalJudgmentModel.claim_id == judgment.claim_id,
                    RetrievalJudgmentModel.document_id == judgment.document_id,
                    RetrievalJudgmentModel.annotator_id == annotator_id,
                )
            ).scalar_one_or_none()

            if existing:
                existing.forage_query_id = judgment.forage_query_id
                existing.relevant = judgment.relevant
                existing.retrieval_rank = judgment.retrieval_rank
                existing.notes = judgment.notes
                model = existing
            else:
                model = RetrievalJudgmentModel(
                    claim_id=judgment.claim_id,
                    document_id=judgment.document_id,
                    annotator_id=annotator_id,
                    forage_query_id=judgment.forage_query_id,
                    relevant=judgment.relevant,
                    retrieval_rank=judgment.retrieval_rank,
                    notes=judgment.notes,
                )
                session.add(model)

            session.flush()
            return _retrieval_judgment_from_model(model)

    def get_judgments_for_claim(self, claim_id: str) -> list[RetrievalJudgment]:
        """Get all retrieval judgments for a claim."""
        with session_scope() as session:
            stmt = (
                select(RetrievalJudgmentModel)
                .where(RetrievalJudgmentModel.claim_id == claim_id)
                .order_by(RetrievalJudgmentModel.retrieval_rank)
            )
            models = session.execute(stmt).scalars().all()
            return [_retrieval_judgment_from_model(m) for m in models]

    def get_judgment(
        self, claim_id: str, document_id: str, annotator_id: str | None = None
    ) -> RetrievalJudgment | None:
        """Get a specific retrieval judgment."""
        annotator_id = annotator_id or "system"
        with session_scope() as session:
            model = session.execute(
                select(RetrievalJudgmentModel).where(
                    RetrievalJudgmentModel.claim_id == claim_id,
                    RetrievalJudgmentModel.document_id == document_id,
                    RetrievalJudgmentModel.annotator_id == annotator_id,
                )
            ).scalar_one_or_none()
            if model:
                return _retrieval_judgment_from_model(model)
        return None

    def delete_retrieval_judgment(self, claim_id: str, document_id: str, annotator_id: str | None = None) -> bool:
        """Delete a retrieval judgment."""
        annotator_id = annotator_id or "system"
        with session_scope() as session:
            model = session.execute(
                select(RetrievalJudgmentModel).where(
                    RetrievalJudgmentModel.claim_id == claim_id,
                    RetrievalJudgmentModel.document_id == document_id,
                    RetrievalJudgmentModel.annotator_id == annotator_id,
                )
            ).scalar_one_or_none()
            if model:
                session.delete(model)
                return True
        return False

    # --- Forage Strategy methods ---

    def upsert_forage_strategy(self, strategy: ForageStrategyRecord) -> ForageStrategyRecord:
        """Insert or update a forage strategy."""
        with session_scope() as session:
            existing = session.execute(
                select(ForageStrategyModel).where(
                    ForageStrategyModel.forage_strategy_id == strategy.forage_strategy_id
                )
            ).scalar_one_or_none()

            captured_at = (
                datetime.fromisoformat(strategy.captured_at)
                if strategy.captured_at
                else datetime.now(timezone.utc)
            )

            if existing:
                existing.claim_id = strategy.claim_id
                existing.claim_text = strategy.claim_text
                existing.perspective = strategy.perspective
                existing.generator_version = strategy.generator_version
                existing.generator = strategy.generator
                existing.claim_type = strategy.claim_type
                existing.providers = strategy.providers
                existing.context = strategy.context
                existing.fallback_reason = strategy.fallback_reason
                existing.claim_decomposition = strategy.claim_decomposition
                existing.polarity_reversal = strategy.polarity_reversal
                existing.schema_plan = strategy.schema_plan
                model = existing
            else:
                model = ForageStrategyModel(
                    forage_strategy_id=strategy.forage_strategy_id,
                    claim_id=strategy.claim_id,
                    claim_text=strategy.claim_text,
                    mode=strategy.mode,
                    perspective=strategy.perspective,
                    generator_version=strategy.generator_version,
                    generator=strategy.generator,
                    claim_type=strategy.claim_type,
                    providers=strategy.providers,
                    context=strategy.context,
                    source=strategy.source,
                    fallback_reason=strategy.fallback_reason,
                    claim_decomposition=strategy.claim_decomposition,
                    polarity_reversal=strategy.polarity_reversal,
                    schema_plan=strategy.schema_plan,
                    captured_at=captured_at,
                )
                session.add(model)

            session.flush()
            return _forage_strategy_from_model(model)

    def get_forage_strategy(self, forage_strategy_id: str) -> ForageStrategyRecord | None:
        """Get a forage strategy by ID."""
        with session_scope() as session:
            model = session.execute(
                select(ForageStrategyModel).where(ForageStrategyModel.forage_strategy_id == forage_strategy_id)
            ).scalar_one_or_none()
            if model:
                return _forage_strategy_from_model(model)
        return None

    def get_strategies_for_claim(self, claim_id: str) -> list[ForageStrategyRecord]:
        """Get all forage strategies for a claim."""
        with session_scope() as session:
            stmt = (
                select(ForageStrategyModel)
                .where(ForageStrategyModel.claim_id == claim_id)
                .order_by(ForageStrategyModel.captured_at)
            )
            models = session.execute(stmt).scalars().all()
            return [_forage_strategy_from_model(m) for m in models]

    def list_forage_strategies(self) -> list[ForageStrategyRecord]:
        """List all forage strategies."""
        with session_scope() as session:
            stmt = select(ForageStrategyModel).order_by(ForageStrategyModel.captured_at)
            models = session.execute(stmt).scalars().all()
            return [_forage_strategy_from_model(m) for m in models]

    # --- Forage Query methods ---

    def upsert_forage_query(self, query: ForageQueryRecord) -> ForageQueryRecord:
        """Insert or update a forage query."""
        with session_scope() as session:
            existing = session.execute(
                select(ForageQueryModel).where(ForageQueryModel.forage_query_id == query.forage_query_id)
            ).scalar_one_or_none()

            if existing:
                existing.fixture_id = query.fixture_id
                existing.priority = query.priority
                existing.rank = query.rank
                model = existing
            else:
                model = ForageQueryModel(
                    forage_query_id=query.forage_query_id,
                    forage_strategy_id=query.forage_strategy_id,
                    pool=query.pool,
                    query=query.query,
                    strategy=query.strategy,
                    priority=query.priority,
                    rank=query.rank,
                    providers=query.providers,
                    intent_label=query.intent_label,
                    rationale=query.rationale,
                    retrieval_role=query.retrieval_role,
                    scheme=query.scheme,
                    critical_question_family=query.critical_question_family,
                    target_schema_need_id=query.target_schema_need_id,
                    fixture_id=query.fixture_id,
                )
                session.add(model)

            session.flush()
            return _forage_query_from_model(model)

    def get_queries_for_strategy(self, forage_strategy_id: str) -> list[ForageQueryRecord]:
        """Get all queries for a forage strategy."""
        with session_scope() as session:
            stmt = (
                select(ForageQueryModel)
                .where(ForageQueryModel.forage_strategy_id == forage_strategy_id)
                .order_by(ForageQueryModel.rank)
            )
            models = session.execute(stmt).scalars().all()
            return [_forage_query_from_model(m) for m in models]

    def list_forage_queries(self) -> list[ForageQueryRecord]:
        """List all forage queries."""
        with session_scope() as session:
            stmt = select(ForageQueryModel).order_by(ForageQueryModel.rank)
            models = session.execute(stmt).scalars().all()
            return [_forage_query_from_model(m) for m in models]

    # --- Dataset methods ---

    def get_dataset(self) -> Dataset:
        """Get dataset metadata."""
        with session_scope() as session:
            model = session.execute(select(DatasetModel).where(DatasetModel.id == 1)).scalar_one()
            return _dataset_from_model(model)

    def update_dataset(
        self,
        dataset_version: str | None = None,
        annotation_guidelines_version: str | None = None,
    ) -> Dataset:
        """Update dataset metadata."""
        with session_scope() as session:
            model = session.execute(select(DatasetModel).where(DatasetModel.id == 1)).scalar_one()
            if dataset_version:
                model.dataset_version = dataset_version
            if annotation_guidelines_version:
                model.annotation_guidelines_version = annotation_guidelines_version
            session.flush()
            return _dataset_from_model(model)

    # --- Utility methods ---

    def count_records(self) -> dict[str, int]:
        """Count records in each table."""
        from sqlalchemy import func

        tables = {
            "claim": ClaimModel,
            "claim_document_link": ClaimDocumentLinkModel,
            "document_annotation": DocumentAnnotationModel,
            "gold_span": GoldSpanModel,
            "claim_span_label": ClaimSpanLabelModel,
            "retrieval_judgment": RetrievalJudgmentModel,
            "forage_strategy": ForageStrategyModel,
            "forage_query": ForageQueryModel,
        }
        counts = {}
        with session_scope() as session:
            for name, model_cls in tables.items():
                count = session.execute(select(func.count()).select_from(model_cls)).scalar()
                counts[name] = count or 0
        return counts
