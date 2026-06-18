"""EU-3 — Gold store (SQLite). Implements the design-note §4 schema.

Record types (see docs/gold-eval-design.md §4):
  - claim                (id, text, family, proof_standard, split)
  - claim_document_link  (claim_id, document_id, origin=search|manual)  -- gates T1/T3 eligibility
  - document_annotation  (document_id, fixture_id, exhaustively_annotated, lost_evidence_flag)
  - gold_span            (span_id, document_id, offsets, text, is_claim_bearing, label_source, ...)
  - claim_span_label     (claim_id, span_id, relevant_to_claim, [stance, strength_ordinal — v2])
  - retrieval_judgment   (claim_id, document_id, forage_query_id, relevant, retrieval_rank)
  - forage_strategy      (forage_strategy_id, claim_id, mode, generator_version, source)
  - forage_query         (forage_query_id, forage_strategy_id, pool, query, fixture_id, ...)
  - dataset              (dataset_version, schema_version, annotation_guidelines_version)

Two judgment frames: span-intrinsic (`is_claim_bearing`, reusable across claims) lives on
`gold_span`; claim-conditioned (`relevant_to_claim`, stance, strength) lives on `claim_span_label`.
Gold records reference fixtures by hash. This store is the tool's OWN store — never a
production database.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .config import Settings, get_settings

# Schema version for migrations
SCHEMA_VERSION = "gold_v1"

# SQL schema
SCHEMA_SQL = """
-- Dataset metadata
CREATE TABLE IF NOT EXISTS dataset (
    id INTEGER PRIMARY KEY CHECK (id = 1),  -- singleton
    dataset_version TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    annotation_guidelines_version TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Claims (debate propositions)
CREATE TABLE IF NOT EXISTS claim (
    claim_id TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    family TEXT CHECK (family IN ('policy', 'factual', 'comparative', 'predictive', 'causal', 'existence')),
    proof_standard TEXT CHECK (proof_standard IN ('PE', 'CCE', 'BRD', 'DV')),
    split TEXT CHECK (split IN ('train', 'dev', 'test')) DEFAULT 'train',
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Claim-document links (gates T1/T3 eligibility)
CREATE TABLE IF NOT EXISTS claim_document_link (
    claim_id TEXT NOT NULL REFERENCES claim(claim_id),
    document_id TEXT NOT NULL,  -- content-addressed by source_text_hash
    origin TEXT CHECK (origin IN ('search', 'manual')) NOT NULL,
    fixture_id TEXT,  -- which fixture surfaced this link
    notes TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY (claim_id, document_id)
);

-- Document annotations (per document, claim-independent)
CREATE TABLE IF NOT EXISTS document_annotation (
    document_id TEXT PRIMARY KEY,  -- content-addressed by source_text_hash
    fixture_id TEXT NOT NULL,
    exhaustively_annotated INTEGER DEFAULT 0,  -- bool: every claim-bearing span marked
    lost_evidence_flag INTEGER DEFAULT 0,  -- bool: material evidence absent from source_text
    lost_evidence_note TEXT,
    annotator_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Gold spans (span-intrinsic, claim-independent, reusable)
CREATE TABLE IF NOT EXISTS gold_span (
    span_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,  -- content-addressed by source_text_hash
    fixture_id TEXT NOT NULL,
    char_offset INTEGER NOT NULL,
    char_length INTEGER NOT NULL,
    text TEXT NOT NULL,  -- verbatim copy for integrity check
    is_claim_bearing INTEGER,  -- bool: well-formed, verifiable statement
    label_source TEXT CHECK (label_source IN ('pipeline_prefill', 'pipeline_prefill_corrected', 'human_authored')),
    annotator_id TEXT,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_gold_span_document ON gold_span(document_id);

-- Claim-span labels (claim-conditioned: germaneness + stance/strength)
CREATE TABLE IF NOT EXISTS claim_span_label (
    claim_id TEXT NOT NULL REFERENCES claim(claim_id),
    span_id TEXT NOT NULL REFERENCES gold_span(span_id),
    relevant_to_claim INTEGER,  -- bool or graded: is this span germane to this claim
    stance TEXT CHECK (stance IN ('PRO', 'CON', 'NEUTRAL')),  -- v2: optional
    strength_ordinal TEXT CHECK (strength_ordinal IN ('none', 'weak', 'moderate', 'strong')),  -- v2: optional
    annotator_id TEXT,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (claim_id, span_id)
);

-- Retrieval judgments (T1: claim × document)
CREATE TABLE IF NOT EXISTS retrieval_judgment (
    claim_id TEXT NOT NULL REFERENCES claim(claim_id),
    document_id TEXT NOT NULL,  -- content-addressed by source_text_hash
    forage_query_id TEXT,  -- which query surfaced it; null for manual/Mode-B
    relevant INTEGER,  -- bool or graded 0-3
    retrieval_rank INTEGER,  -- rank in captured results
    annotator_id TEXT,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (claim_id, document_id)
);

-- Forage strategies (db8r-mcts generator output)
CREATE TABLE IF NOT EXISTS forage_strategy (
    forage_strategy_id TEXT PRIMARY KEY,
    claim_id TEXT REFERENCES claim(claim_id),
    claim_text TEXT,  -- denormalized for strategies without a claim record
    mode TEXT CHECK (mode IN ('pregame', 'reactive')) NOT NULL,
    perspective TEXT CHECK (perspective IN ('supports_claim', 'contradicts_claim')),
    generator_version TEXT NOT NULL,
    generator TEXT,
    claim_type TEXT,
    providers TEXT,  -- JSON array
    context TEXT,  -- JSON: reactive only (role, proof_standard, target, move)
    source TEXT CHECK (source IN ('mc5_endpoint', 'debate_trace')) NOT NULL,
    fallback_reason TEXT,
    claim_decomposition TEXT,  -- JSON
    polarity_reversal TEXT,  -- JSON
    schema_plan TEXT,  -- JSON
    captured_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_forage_strategy_claim ON forage_strategy(claim_id);

-- Forage queries (one query in a strategy)
CREATE TABLE IF NOT EXISTS forage_query (
    forage_query_id TEXT PRIMARY KEY,
    forage_strategy_id TEXT NOT NULL REFERENCES forage_strategy(forage_strategy_id),
    pool TEXT CHECK (pool IN ('PRO', 'CON')) NOT NULL,
    query TEXT NOT NULL,
    strategy TEXT,
    priority REAL,
    rank INTEGER,
    providers TEXT,  -- JSON array
    intent_label TEXT,
    rationale TEXT,
    retrieval_role TEXT,
    scheme TEXT,
    critical_question_family TEXT,
    target_schema_need_id TEXT,
    fixture_id TEXT,  -- the /search fixture produced by replaying this query
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_forage_query_strategy ON forage_query(forage_strategy_id);
CREATE INDEX IF NOT EXISTS idx_forage_query_fixture ON forage_query(fixture_id);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _generate_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


# --- Dataclasses for records ---


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


# --- Store class ---


class GoldStore:
    """SQLite store for gold annotations."""

    def __init__(self, db_path: str | Path | None = None, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.db_path = Path(db_path) if db_path else self.settings.gold_db_path
        self._ensure_db_dir()
        self._init_schema()

    def _ensure_db_dir(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA_SQL)
            # Initialize dataset singleton if not exists
            cursor = conn.execute("SELECT COUNT(*) FROM dataset")
            if cursor.fetchone()[0] == 0:
                now = _now_iso()
                conn.execute(
                    "INSERT INTO dataset (id, dataset_version, schema_version, created_at, updated_at) VALUES (1, ?, ?, ?, ?)",
                    ("v1.0", SCHEMA_VERSION, now, now),
                )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # --- Claim methods ---

    def upsert_claim(self, claim: Claim) -> Claim:
        """Insert or update a claim."""
        now = _now_iso()
        if not claim.created_at:
            claim.created_at = now
        claim.updated_at = now

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO claim (claim_id, text, family, proof_standard, split, notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(claim_id) DO UPDATE SET
                    text = excluded.text,
                    family = excluded.family,
                    proof_standard = excluded.proof_standard,
                    split = excluded.split,
                    notes = excluded.notes,
                    updated_at = excluded.updated_at
                """,
                (
                    claim.claim_id,
                    claim.text,
                    claim.family,
                    claim.proof_standard,
                    claim.split,
                    claim.notes,
                    claim.created_at,
                    claim.updated_at,
                ),
            )
        return claim

    def get_claim(self, claim_id: str) -> Claim | None:
        """Get a claim by ID."""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM claim WHERE claim_id = ?", (claim_id,)).fetchone()
            if row:
                return Claim(**dict(row))
        return None

    def list_claims(self, split: str | None = None, family: str | None = None) -> list[Claim]:
        """List claims, optionally filtered by split and/or family."""
        with self._connect() as conn:
            query = "SELECT * FROM claim WHERE 1=1"
            params: list[Any] = []
            if split:
                query += " AND split = ?"
                params.append(split)
            if family:
                query += " AND family = ?"
                params.append(family)
            query += " ORDER BY claim_id"
            rows = conn.execute(query, params).fetchall()
            return [Claim(**dict(row)) for row in rows]

    # --- Claim-Document Link methods ---

    def upsert_claim_document_link(self, link: ClaimDocumentLink) -> ClaimDocumentLink:
        """Insert or update a claim-document link."""
        if not link.created_at:
            link.created_at = _now_iso()

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO claim_document_link (claim_id, document_id, origin, fixture_id, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(claim_id, document_id) DO UPDATE SET
                    origin = excluded.origin,
                    fixture_id = excluded.fixture_id,
                    notes = excluded.notes
                """,
                (link.claim_id, link.document_id, link.origin, link.fixture_id, link.notes, link.created_at),
            )
        return link

    def get_documents_for_claim(self, claim_id: str) -> list[ClaimDocumentLink]:
        """Get all document links for a claim."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM claim_document_link WHERE claim_id = ? ORDER BY created_at", (claim_id,)
            ).fetchall()
            return [ClaimDocumentLink(**dict(row)) for row in rows]

    # --- Document Annotation methods ---

    def upsert_document_annotation(self, annotation: DocumentAnnotation) -> DocumentAnnotation:
        """Insert or update a document annotation."""
        now = _now_iso()
        if not annotation.created_at:
            annotation.created_at = now
        annotation.updated_at = now

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO document_annotation (document_id, fixture_id, exhaustively_annotated,
                    lost_evidence_flag, lost_evidence_note, annotator_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(document_id) DO UPDATE SET
                    exhaustively_annotated = excluded.exhaustively_annotated,
                    lost_evidence_flag = excluded.lost_evidence_flag,
                    lost_evidence_note = excluded.lost_evidence_note,
                    annotator_id = excluded.annotator_id,
                    updated_at = excluded.updated_at
                """,
                (
                    annotation.document_id,
                    annotation.fixture_id,
                    int(annotation.exhaustively_annotated),
                    int(annotation.lost_evidence_flag),
                    annotation.lost_evidence_note,
                    annotation.annotator_id,
                    annotation.created_at,
                    annotation.updated_at,
                ),
            )
        return annotation

    def get_document_annotation(self, document_id: str) -> DocumentAnnotation | None:
        """Get annotation for a document."""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM document_annotation WHERE document_id = ?", (document_id,)).fetchone()
            if row:
                d = dict(row)
                d["exhaustively_annotated"] = bool(d["exhaustively_annotated"])
                d["lost_evidence_flag"] = bool(d["lost_evidence_flag"])
                return DocumentAnnotation(**d)
        return None

    # --- Gold Span methods ---

    def upsert_gold_span(self, span: GoldSpan) -> GoldSpan:
        """Insert or update a gold span."""
        now = _now_iso()
        if not span.created_at:
            span.created_at = now
        span.updated_at = now

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO gold_span (span_id, document_id, fixture_id, char_offset, char_length,
                    text, is_claim_bearing, label_source, annotator_id, notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(span_id) DO UPDATE SET
                    is_claim_bearing = excluded.is_claim_bearing,
                    label_source = excluded.label_source,
                    annotator_id = excluded.annotator_id,
                    notes = excluded.notes,
                    updated_at = excluded.updated_at
                """,
                (
                    span.span_id,
                    span.document_id,
                    span.fixture_id,
                    span.char_offset,
                    span.char_length,
                    span.text,
                    int(span.is_claim_bearing) if span.is_claim_bearing is not None else None,
                    span.label_source,
                    span.annotator_id,
                    span.notes,
                    span.created_at,
                    span.updated_at,
                ),
            )
        return span

    def get_gold_span(self, span_id: str) -> GoldSpan | None:
        """Get a gold span by ID."""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM gold_span WHERE span_id = ?", (span_id,)).fetchone()
            if row:
                d = dict(row)
                d["is_claim_bearing"] = bool(d["is_claim_bearing"]) if d["is_claim_bearing"] is not None else None
                return GoldSpan(**d)
        return None

    def get_spans_for_document(self, document_id: str) -> list[GoldSpan]:
        """Get all gold spans for a document."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM gold_span WHERE document_id = ? ORDER BY char_offset", (document_id,)
            ).fetchall()
            spans = []
            for row in rows:
                d = dict(row)
                d["is_claim_bearing"] = bool(d["is_claim_bearing"]) if d["is_claim_bearing"] is not None else None
                spans.append(GoldSpan(**d))
            return spans

    # --- Claim-Span Label methods ---

    def upsert_claim_span_label(self, label: ClaimSpanLabel) -> ClaimSpanLabel:
        """Insert or update a claim-span label."""
        now = _now_iso()
        if not label.created_at:
            label.created_at = now
        label.updated_at = now

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO claim_span_label (claim_id, span_id, relevant_to_claim, stance,
                    strength_ordinal, annotator_id, notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(claim_id, span_id) DO UPDATE SET
                    relevant_to_claim = excluded.relevant_to_claim,
                    stance = excluded.stance,
                    strength_ordinal = excluded.strength_ordinal,
                    annotator_id = excluded.annotator_id,
                    notes = excluded.notes,
                    updated_at = excluded.updated_at
                """,
                (
                    label.claim_id,
                    label.span_id,
                    int(label.relevant_to_claim) if label.relevant_to_claim is not None else None,
                    label.stance,
                    label.strength_ordinal,
                    label.annotator_id,
                    label.notes,
                    label.created_at,
                    label.updated_at,
                ),
            )
        return label

    def get_labels_for_span(self, span_id: str) -> list[ClaimSpanLabel]:
        """Get all claim labels for a span."""
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM claim_span_label WHERE span_id = ?", (span_id,)).fetchall()
            labels = []
            for row in rows:
                d = dict(row)
                d["relevant_to_claim"] = bool(d["relevant_to_claim"]) if d["relevant_to_claim"] is not None else None
                labels.append(ClaimSpanLabel(**d))
            return labels

    def get_labels_for_claim(self, claim_id: str) -> list[ClaimSpanLabel]:
        """Get all span labels for a claim."""
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM claim_span_label WHERE claim_id = ?", (claim_id,)).fetchall()
            labels = []
            for row in rows:
                d = dict(row)
                d["relevant_to_claim"] = bool(d["relevant_to_claim"]) if d["relevant_to_claim"] is not None else None
                labels.append(ClaimSpanLabel(**d))
            return labels

    # --- Retrieval Judgment methods ---

    def upsert_retrieval_judgment(self, judgment: RetrievalJudgment) -> RetrievalJudgment:
        """Insert or update a retrieval judgment."""
        now = _now_iso()
        if not judgment.created_at:
            judgment.created_at = now
        judgment.updated_at = now

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO retrieval_judgment (claim_id, document_id, forage_query_id, relevant,
                    retrieval_rank, annotator_id, notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(claim_id, document_id) DO UPDATE SET
                    forage_query_id = excluded.forage_query_id,
                    relevant = excluded.relevant,
                    retrieval_rank = excluded.retrieval_rank,
                    annotator_id = excluded.annotator_id,
                    notes = excluded.notes,
                    updated_at = excluded.updated_at
                """,
                (
                    judgment.claim_id,
                    judgment.document_id,
                    judgment.forage_query_id,
                    judgment.relevant,
                    judgment.retrieval_rank,
                    judgment.annotator_id,
                    judgment.notes,
                    judgment.created_at,
                    judgment.updated_at,
                ),
            )
        return judgment

    def get_judgments_for_claim(self, claim_id: str) -> list[RetrievalJudgment]:
        """Get all retrieval judgments for a claim."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM retrieval_judgment WHERE claim_id = ? ORDER BY retrieval_rank", (claim_id,)
            ).fetchall()
            return [RetrievalJudgment(**dict(row)) for row in rows]

    # --- Forage Strategy methods ---

    def upsert_forage_strategy(self, strategy: ForageStrategyRecord) -> ForageStrategyRecord:
        """Insert or update a forage strategy."""
        now = _now_iso()
        if not strategy.created_at:
            strategy.created_at = now

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO forage_strategy (forage_strategy_id, claim_id, claim_text, mode, perspective,
                    generator_version, generator, claim_type, providers, context, source, fallback_reason,
                    claim_decomposition, polarity_reversal, schema_plan, captured_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(forage_strategy_id) DO UPDATE SET
                    claim_id = excluded.claim_id,
                    claim_text = excluded.claim_text,
                    perspective = excluded.perspective,
                    generator_version = excluded.generator_version,
                    generator = excluded.generator,
                    claim_type = excluded.claim_type,
                    providers = excluded.providers,
                    context = excluded.context,
                    fallback_reason = excluded.fallback_reason,
                    claim_decomposition = excluded.claim_decomposition,
                    polarity_reversal = excluded.polarity_reversal,
                    schema_plan = excluded.schema_plan
                """,
                (
                    strategy.forage_strategy_id,
                    strategy.claim_id,
                    strategy.claim_text,
                    strategy.mode,
                    strategy.perspective,
                    strategy.generator_version,
                    strategy.generator,
                    strategy.claim_type,
                    json.dumps(strategy.providers) if strategy.providers else None,
                    json.dumps(strategy.context) if strategy.context else None,
                    strategy.source,
                    strategy.fallback_reason,
                    json.dumps(strategy.claim_decomposition) if strategy.claim_decomposition else None,
                    json.dumps(strategy.polarity_reversal) if strategy.polarity_reversal else None,
                    json.dumps(strategy.schema_plan) if strategy.schema_plan else None,
                    strategy.captured_at,
                    strategy.created_at,
                ),
            )
        return strategy

    def get_forage_strategy(self, forage_strategy_id: str) -> ForageStrategyRecord | None:
        """Get a forage strategy by ID."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM forage_strategy WHERE forage_strategy_id = ?", (forage_strategy_id,)
            ).fetchone()
            if row:
                d = dict(row)
                d["providers"] = json.loads(d["providers"]) if d["providers"] else []
                d["context"] = json.loads(d["context"]) if d["context"] else None
                d["claim_decomposition"] = json.loads(d["claim_decomposition"]) if d["claim_decomposition"] else None
                d["polarity_reversal"] = json.loads(d["polarity_reversal"]) if d["polarity_reversal"] else None
                d["schema_plan"] = json.loads(d["schema_plan"]) if d["schema_plan"] else None
                return ForageStrategyRecord(**d)
        return None

    def get_strategies_for_claim(self, claim_id: str) -> list[ForageStrategyRecord]:
        """Get all forage strategies for a claim."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM forage_strategy WHERE claim_id = ? ORDER BY captured_at", (claim_id,)
            ).fetchall()
            strategies = []
            for row in rows:
                d = dict(row)
                d["providers"] = json.loads(d["providers"]) if d["providers"] else []
                d["context"] = json.loads(d["context"]) if d["context"] else None
                d["claim_decomposition"] = json.loads(d["claim_decomposition"]) if d["claim_decomposition"] else None
                d["polarity_reversal"] = json.loads(d["polarity_reversal"]) if d["polarity_reversal"] else None
                d["schema_plan"] = json.loads(d["schema_plan"]) if d["schema_plan"] else None
                strategies.append(ForageStrategyRecord(**d))
            return strategies

    # --- Forage Query methods ---

    def upsert_forage_query(self, query: ForageQueryRecord) -> ForageQueryRecord:
        """Insert or update a forage query."""
        if not query.created_at:
            query.created_at = _now_iso()

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO forage_query (forage_query_id, forage_strategy_id, pool, query, strategy,
                    priority, rank, providers, intent_label, rationale, retrieval_role, scheme,
                    critical_question_family, target_schema_need_id, fixture_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(forage_query_id) DO UPDATE SET
                    fixture_id = excluded.fixture_id,
                    priority = excluded.priority,
                    rank = excluded.rank
                """,
                (
                    query.forage_query_id,
                    query.forage_strategy_id,
                    query.pool,
                    query.query,
                    query.strategy,
                    query.priority,
                    query.rank,
                    json.dumps(query.providers) if query.providers else None,
                    query.intent_label,
                    query.rationale,
                    query.retrieval_role,
                    query.scheme,
                    query.critical_question_family,
                    query.target_schema_need_id,
                    query.fixture_id,
                    query.created_at,
                ),
            )
        return query

    def get_queries_for_strategy(self, forage_strategy_id: str) -> list[ForageQueryRecord]:
        """Get all queries for a forage strategy."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM forage_query WHERE forage_strategy_id = ? ORDER BY rank", (forage_strategy_id,)
            ).fetchall()
            queries = []
            for row in rows:
                d = dict(row)
                d["providers"] = json.loads(d["providers"]) if d["providers"] else []
                queries.append(ForageQueryRecord(**d))
            return queries

    # --- Dataset methods ---

    def get_dataset(self) -> Dataset:
        """Get dataset metadata."""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM dataset WHERE id = 1").fetchone()
            d = dict(row)
            d.pop("id", None)  # Exclude singleton id from dataclass
            return Dataset(**d)

    def update_dataset(
        self,
        dataset_version: str | None = None,
        annotation_guidelines_version: str | None = None,
    ) -> Dataset:
        """Update dataset metadata."""
        now = _now_iso()
        with self._connect() as conn:
            if dataset_version:
                conn.execute("UPDATE dataset SET dataset_version = ?, updated_at = ? WHERE id = 1", (dataset_version, now))
            if annotation_guidelines_version:
                conn.execute(
                    "UPDATE dataset SET annotation_guidelines_version = ?, updated_at = ? WHERE id = 1",
                    (annotation_guidelines_version, now),
                )
            return self.get_dataset()

    # --- Utility methods ---

    def count_records(self) -> dict[str, int]:
        """Count records in each table."""
        tables = [
            "claim",
            "claim_document_link",
            "document_annotation",
            "gold_span",
            "claim_span_label",
            "retrieval_judgment",
            "forage_strategy",
            "forage_query",
        ]
        counts = {}
        with self._connect() as conn:
            for table in tables:
                cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
                counts[table] = cursor.fetchone()[0]
        return counts
