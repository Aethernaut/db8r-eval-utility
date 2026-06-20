"""EU-5 — Scorer. Computes v1 metrics by joining gold records to fixtures (offline).

v1 metrics (README §7; docs/gold-eval-design.md §5). Stance/strength/polarity_error_rate are v2.
  - Retrieval:   recall@k, precision@k, coverage, primary-source coverage
  - Extraction:  TWO precisions (decompose the failure) + germane recall, char-range IoU >= tau (0.5):
                   * well-formedness precision = extracted matching an is_claim_bearing gold span / total extracted
                   * targeting precision (per claim) = extracted matching a relevant_to_claim gold span / total extracted
                   * germane recall (per claim) = matched (is_claim_bearing AND relevant_to_claim) / all such
                 broken out by document-length bucket, content_type, capture_mode
  - Fidelity:    match_method distribution, mean extraction_fidelity, verbatim-locatability rate
  - Coverage:    lost-evidence rate (separate from extractor recall)
  - Exclude fixtures with extraction_status.partial_extraction == true from extraction-recall
    denominators (a truncated doc is not a fair recall target).
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import Settings, get_settings
from .fixtures import LoadedFixture, LoadedSpan, list_fixtures, load_fixture
from .store import GoldSpan, GoldStore


def char_range_iou(a_offset: int, a_len: int, b_offset: int, b_len: int) -> float:
    """Intersection-over-union of two character ranges. Used for gold↔extracted span matching."""
    a0, a1 = a_offset, a_offset + a_len
    b0, b1 = b_offset, b_offset + b_len
    inter = max(0, min(a1, b1) - max(a0, b0))
    union = (a1 - a0) + (b1 - b0) - inter
    return inter / union if union > 0 else 0.0


# --- Result dataclasses ---


@dataclass
class SpanMatch:
    """A matched pair of gold span and extracted span."""

    gold_span: GoldSpan
    extracted_span: LoadedSpan
    iou: float


@dataclass
class RetrievalMetrics:
    """Retrieval metrics for a single claim or query."""

    total_retrieved: int = 0
    total_relevant: int = 0
    relevant_retrieved: int = 0
    recall_at_k: dict[int, float] = field(default_factory=dict)  # k -> recall
    precision_at_k: dict[int, float] = field(default_factory=dict)  # k -> precision

    @property
    def recall(self) -> float:
        """Overall recall."""
        return self.relevant_retrieved / self.total_relevant if self.total_relevant > 0 else 0.0

    @property
    def precision(self) -> float:
        """Overall precision."""
        return self.relevant_retrieved / self.total_retrieved if self.total_retrieved > 0 else 0.0


@dataclass
class ExtractionMetrics:
    """Extraction metrics for a document or claim."""

    total_extracted: int = 0
    total_gold_claim_bearing: int = 0
    total_gold_relevant: int = 0  # For claim-level: is_claim_bearing AND relevant_to_claim

    matched_claim_bearing: int = 0  # Extracted matching is_claim_bearing gold span
    matched_relevant: int = 0  # Extracted matching relevant_to_claim gold span

    @property
    def well_formedness_precision(self) -> float:
        """Precision for well-formed spans (extracted matching is_claim_bearing)."""
        return self.matched_claim_bearing / self.total_extracted if self.total_extracted > 0 else 0.0

    @property
    def targeting_precision(self) -> float:
        """Precision for targeting (extracted matching relevant_to_claim)."""
        return self.matched_relevant / self.total_extracted if self.total_extracted > 0 else 0.0

    @property
    def well_formed_recall(self) -> float:
        """Recall for well-formed spans."""
        return self.matched_claim_bearing / self.total_gold_claim_bearing if self.total_gold_claim_bearing > 0 else 0.0

    @property
    def germane_recall(self) -> float:
        """Recall for germane spans (is_claim_bearing AND relevant_to_claim)."""
        return self.matched_relevant / self.total_gold_relevant if self.total_gold_relevant > 0 else 0.0

    @property
    def f1_germane(self) -> float:
        """F1 score for germane spans."""
        p = self.targeting_precision
        r = self.germane_recall
        return 2 * p * r / (p + r) if (p + r) > 0 else 0.0


@dataclass
class FidelityMetrics:
    """Fidelity metrics for extracted spans."""

    match_method_counts: dict[str, int] = field(default_factory=dict)
    extraction_fidelities: list[float] = field(default_factory=list)
    total_spans: int = 0
    verbatim_locatable: int = 0

    @property
    def match_method_distribution(self) -> dict[str, float]:
        """Distribution of match methods."""
        if self.total_spans == 0:
            return {}
        return {k: v / self.total_spans for k, v in self.match_method_counts.items()}

    @property
    def mean_extraction_fidelity(self) -> float:
        """Mean extraction fidelity."""
        if not self.extraction_fidelities:
            return 0.0
        return sum(self.extraction_fidelities) / len(self.extraction_fidelities)

    @property
    def verbatim_locatability_rate(self) -> float:
        """Rate of verbatim-locatable spans."""
        return self.verbatim_locatable / self.total_spans if self.total_spans > 0 else 0.0


@dataclass
class CoverageMetrics:
    """Coverage metrics."""

    total_documents: int = 0
    lost_evidence_documents: int = 0
    total_claims: int = 0
    claims_with_germane_doc: int = 0
    claims_with_primary_source: int = 0

    @property
    def lost_evidence_rate(self) -> float:
        """Rate of documents with lost evidence."""
        return self.lost_evidence_documents / self.total_documents if self.total_documents > 0 else 0.0

    @property
    def claim_coverage(self) -> float:
        """Fraction of claims with at least one germane doc."""
        return self.claims_with_germane_doc / self.total_claims if self.total_claims > 0 else 0.0

    @property
    def primary_source_coverage(self) -> float:
        """Fraction of claims with a primary source doc."""
        return self.claims_with_primary_source / self.total_claims if self.total_claims > 0 else 0.0


@dataclass
class ScorerReport:
    """Complete scorer report."""

    # Overall metrics
    retrieval: RetrievalMetrics = field(default_factory=RetrievalMetrics)
    extraction: ExtractionMetrics = field(default_factory=ExtractionMetrics)
    fidelity: FidelityMetrics = field(default_factory=FidelityMetrics)
    coverage: CoverageMetrics = field(default_factory=CoverageMetrics)

    # Per-claim breakouts
    per_claim_retrieval: dict[str, RetrievalMetrics] = field(default_factory=dict)
    per_claim_extraction: dict[str, ExtractionMetrics] = field(default_factory=dict)

    # Breakouts by document characteristics
    by_content_type: dict[str, ExtractionMetrics] = field(default_factory=dict)
    by_length_bucket: dict[str, ExtractionMetrics] = field(default_factory=dict)
    by_capture_mode: dict[str, ExtractionMetrics] = field(default_factory=dict)

    # Metadata
    fixtures_evaluated: int = 0
    fixtures_skipped_partial: int = 0
    gold_spans_total: int = 0
    extracted_spans_total: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "summary": {
                "fixtures_evaluated": self.fixtures_evaluated,
                "fixtures_skipped_partial": self.fixtures_skipped_partial,
                "gold_spans_total": self.gold_spans_total,
                "extracted_spans_total": self.extracted_spans_total,
            },
            "retrieval": {
                "total_retrieved": self.retrieval.total_retrieved,
                "total_relevant": self.retrieval.total_relevant,
                "relevant_retrieved": self.retrieval.relevant_retrieved,
                "recall": self.retrieval.recall,
                "precision": self.retrieval.precision,
                "recall_at_k": self.retrieval.recall_at_k,
                "precision_at_k": self.retrieval.precision_at_k,
            },
            "extraction": {
                "total_extracted": self.extraction.total_extracted,
                "total_gold_claim_bearing": self.extraction.total_gold_claim_bearing,
                "total_gold_relevant": self.extraction.total_gold_relevant,
                "well_formedness_precision": self.extraction.well_formedness_precision,
                "targeting_precision": self.extraction.targeting_precision,
                "well_formed_recall": self.extraction.well_formed_recall,
                "germane_recall": self.extraction.germane_recall,
                "f1_germane": self.extraction.f1_germane,
            },
            "fidelity": {
                "match_method_distribution": self.fidelity.match_method_distribution,
                "mean_extraction_fidelity": self.fidelity.mean_extraction_fidelity,
                "verbatim_locatability_rate": self.fidelity.verbatim_locatability_rate,
                "total_spans": self.fidelity.total_spans,
            },
            "coverage": {
                "lost_evidence_rate": self.coverage.lost_evidence_rate,
                "claim_coverage": self.coverage.claim_coverage,
                "primary_source_coverage": self.coverage.primary_source_coverage,
                "total_documents": self.coverage.total_documents,
                "total_claims": self.coverage.total_claims,
            },
            "breakouts": {
                "by_content_type": {
                    ct: {
                        "well_formedness_precision": m.well_formedness_precision,
                        "well_formed_recall": m.well_formed_recall,
                        "total_extracted": m.total_extracted,
                        "total_gold": m.total_gold_claim_bearing,
                    }
                    for ct, m in self.by_content_type.items()
                },
                "by_length_bucket": {
                    lb: {
                        "well_formedness_precision": m.well_formedness_precision,
                        "well_formed_recall": m.well_formed_recall,
                        "total_extracted": m.total_extracted,
                        "total_gold": m.total_gold_claim_bearing,
                    }
                    for lb, m in self.by_length_bucket.items()
                },
                "by_capture_mode": {
                    cm: {
                        "well_formedness_precision": m.well_formedness_precision,
                        "well_formed_recall": m.well_formed_recall,
                        "total_extracted": m.total_extracted,
                        "total_gold": m.total_gold_claim_bearing,
                    }
                    for cm, m in self.by_capture_mode.items()
                },
            },
        }


# --- Scorer implementation ---


def get_length_bucket(char_len: int) -> str:
    """Categorize document length into buckets."""
    if char_len < 5000:
        return "short (<5k)"
    elif char_len < 20000:
        return "medium (5k-20k)"
    elif char_len < 50000:
        return "long (20k-50k)"
    else:
        return "very_long (50k+)"


def find_span_matches(
    gold_spans: list[GoldSpan],
    extracted_spans: list[LoadedSpan],
    iou_threshold: float = 0.5,
) -> tuple[list[SpanMatch], list[GoldSpan], list[LoadedSpan]]:
    """Find matching spans between gold and extracted based on IoU threshold.

    Returns:
        - matched: list of SpanMatch objects
        - unmatched_gold: gold spans with no match
        - unmatched_extracted: extracted spans with no match
    """
    matched = []
    used_gold = set()
    used_extracted = set()

    # Greedy matching: for each extracted span, find best matching gold span
    for i, ext in enumerate(extracted_spans):
        best_match = None
        best_iou = 0.0
        best_j = -1

        for j, gold in enumerate(gold_spans):
            if j in used_gold:
                continue
            # Must be same document
            if gold.document_id != ext.document_id:
                continue

            iou = char_range_iou(gold.char_offset, gold.char_length, ext.char_offset, ext.char_length)
            if iou >= iou_threshold and iou > best_iou:
                best_match = gold
                best_iou = iou
                best_j = j

        if best_match is not None:
            matched.append(SpanMatch(gold_span=best_match, extracted_span=ext, iou=best_iou))
            used_gold.add(best_j)
            used_extracted.add(i)

    unmatched_gold = [g for j, g in enumerate(gold_spans) if j not in used_gold]
    unmatched_extracted = [e for i, e in enumerate(extracted_spans) if i not in used_extracted]

    return matched, unmatched_gold, unmatched_extracted


def compute_retrieval_at_k(
    retrieved_docs: list[str],  # document IDs in rank order
    relevant_docs: set[str],  # set of relevant document IDs
    k_values: list[int] | None = None,
) -> RetrievalMetrics:
    """Compute retrieval metrics at various k values."""
    if k_values is None:
        k_values = [1, 3, 5, 10, 20]

    metrics = RetrievalMetrics(
        total_retrieved=len(retrieved_docs),
        total_relevant=len(relevant_docs),
    )

    relevant_found = 0
    for i, doc_id in enumerate(retrieved_docs):
        if doc_id in relevant_docs:
            relevant_found += 1

        k = i + 1
        if k in k_values:
            metrics.recall_at_k[k] = relevant_found / len(relevant_docs) if relevant_docs else 0.0
            metrics.precision_at_k[k] = relevant_found / k

    metrics.relevant_retrieved = sum(1 for d in retrieved_docs if d in relevant_docs)

    return metrics


class Scorer:
    """Computes v1 metrics by joining gold records to fixtures."""

    def __init__(
        self,
        store: GoldStore | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.store = store or GoldStore(settings=self.settings)
        self.iou_threshold = self.settings.span_match_iou_threshold
        self.top_k = self.settings.retrieval_top_k

    def score_fixture(
        self,
        fixture: LoadedFixture,
        claim_id: str | None = None,
    ) -> tuple[ExtractionMetrics, FidelityMetrics]:
        """Score a single fixture's extraction metrics.

        Args:
            fixture: The loaded fixture
            claim_id: If provided, compute claim-specific targeting metrics

        Returns:
            Tuple of (extraction_metrics, fidelity_metrics)
        """
        extraction = ExtractionMetrics()
        fidelity = FidelityMetrics()

        # Collect all gold spans for documents in this fixture
        gold_spans_by_doc: dict[str, list[GoldSpan]] = {}
        for doc in fixture.documents:
            spans = self.store.get_spans_for_document(doc.source_text_hash)
            if spans:
                gold_spans_by_doc[doc.source_text_hash] = spans

        # Collect extracted spans
        extracted_spans = fixture.spans

        # Compute fidelity metrics from extracted spans
        fidelity.total_spans = len(extracted_spans)
        for ext in extracted_spans:
            # Match method distribution
            if ext.match_method:
                fidelity.match_method_counts[ext.match_method] = (
                    fidelity.match_method_counts.get(ext.match_method, 0) + 1
                )

            # Extraction fidelity
            if ext.extraction_fidelity is not None:
                fidelity.extraction_fidelities.append(ext.extraction_fidelity)

            # Verbatim locatability
            doc = fixture.get_document(ext.document_id)
            if doc and ext.verbatim_span:
                if ext.verbatim_span in doc.source_text:
                    fidelity.verbatim_locatable += 1

        # Flatten gold spans for matching
        all_gold_spans = []
        for doc_hash, spans in gold_spans_by_doc.items():
            # Map document hash to document ID for matching
            doc = fixture.get_document_by_hash(doc_hash)
            if doc:
                for span in spans:
                    # Create a copy with document_id matching fixture's convention
                    all_gold_spans.append(span)

        # Also need to map extracted spans to use source_text_hash for matching
        # Create mapping from fixture document_id to source_text_hash
        doc_id_to_hash = {d.document_id: d.source_text_hash for d in fixture.documents}

        # Adjust extracted spans to use source_text_hash as document_id for matching
        adjusted_extracted = []
        for ext in extracted_spans:
            if ext.document_id in doc_id_to_hash:
                # Create a new span object with hash as document_id
                adjusted = LoadedSpan(
                    claim_id=ext.claim_id,
                    document_id=doc_id_to_hash[ext.document_id],
                    text=ext.text,
                    char_offset=ext.char_offset,
                    char_length=ext.char_length,
                    extraction_fidelity=ext.extraction_fidelity,
                    match_method=ext.match_method,
                    source_assertion_opinion=ext.source_assertion_opinion,
                    claimset_orientation=ext.claimset_orientation,
                    relevance_score=ext.relevance_score,
                    verbatim_span=ext.verbatim_span,
                )
                adjusted_extracted.append(adjusted)

        extraction.total_extracted = len(adjusted_extracted)

        # Find matches
        matches, unmatched_gold, _ = find_span_matches(
            all_gold_spans,
            adjusted_extracted,
            self.iou_threshold,
        )

        # Count claim-bearing matches
        claim_bearing_gold = [g for g in all_gold_spans if g.is_claim_bearing]
        extraction.total_gold_claim_bearing = len(claim_bearing_gold)

        matched_gold_ids = {m.gold_span.span_id for m in matches}
        extraction.matched_claim_bearing = sum(
            1 for g in claim_bearing_gold if g.span_id in matched_gold_ids
        )

        # If claim_id provided, compute claim-specific metrics
        if claim_id:
            # Get claim-span labels for this claim
            labels = self.store.get_labels_for_claim(claim_id)
            relevant_span_ids = {
                label.span_id for label in labels if label.relevant_to_claim
            }

            # Gold spans that are both claim-bearing AND relevant to this claim
            germane_gold = [
                g for g in claim_bearing_gold if g.span_id in relevant_span_ids
            ]
            extraction.total_gold_relevant = len(germane_gold)

            # Matched spans that are relevant to the claim
            extraction.matched_relevant = sum(
                1 for m in matches if m.gold_span.span_id in relevant_span_ids
            )

        return extraction, fidelity

    def score_claim_retrieval(self, claim_id: str) -> RetrievalMetrics:
        """Score retrieval metrics for a single claim.

        Uses retrieval judgments from the gold store.
        """
        judgments = self.store.get_judgments_for_claim(claim_id)

        # Get documents in rank order
        sorted_judgments = sorted(judgments, key=lambda j: j.retrieval_rank or 999999)
        retrieved_docs = [j.document_id for j in sorted_judgments]

        # Get relevant documents
        relevant_docs = {j.document_id for j in judgments if j.relevant and j.relevant > 0}

        return compute_retrieval_at_k(
            retrieved_docs,
            relevant_docs,
            k_values=[1, 3, 5, 10, self.top_k],
        )

    def score_all(
        self,
        fixtures_dir: Path | None = None,
        skip_partial: bool = True,
    ) -> ScorerReport:
        """Score all fixtures and produce a complete report.

        Args:
            fixtures_dir: Directory containing fixtures (default: settings.fixtures_dir)
            skip_partial: If True, exclude fixtures with partial extraction from recall denominators

        Returns:
            Complete ScorerReport
        """
        fixtures_dir = fixtures_dir or self.settings.fixtures_dir
        report = ScorerReport()

        # Load all fixtures
        fixture_paths = list_fixtures(fixtures_dir)

        # Track aggregated metrics
        all_extraction = ExtractionMetrics()
        all_fidelity = FidelityMetrics()

        # Content type / length / mode breakouts
        by_content_type: dict[str, ExtractionMetrics] = defaultdict(ExtractionMetrics)
        by_length_bucket: dict[str, ExtractionMetrics] = defaultdict(ExtractionMetrics)
        by_capture_mode: dict[str, ExtractionMetrics] = defaultdict(ExtractionMetrics)

        for path in fixture_paths:
            try:
                fixture = load_fixture(path, verify_hashes=False, verify_spans=False)
            except Exception:
                continue

            # Check for partial extraction
            if skip_partial and fixture.has_partial_extraction():
                report.fixtures_skipped_partial += 1
                continue

            report.fixtures_evaluated += 1

            # Score this fixture
            extraction, fidelity = self.score_fixture(fixture)

            # Aggregate extraction metrics
            all_extraction.total_extracted += extraction.total_extracted
            all_extraction.total_gold_claim_bearing += extraction.total_gold_claim_bearing
            all_extraction.matched_claim_bearing += extraction.matched_claim_bearing

            # Aggregate fidelity metrics
            all_fidelity.total_spans += fidelity.total_spans
            all_fidelity.verbatim_locatable += fidelity.verbatim_locatable
            all_fidelity.extraction_fidelities.extend(fidelity.extraction_fidelities)
            for method, count in fidelity.match_method_counts.items():
                all_fidelity.match_method_counts[method] = (
                    all_fidelity.match_method_counts.get(method, 0) + count
                )

            # Per-document breakouts
            for doc in fixture.documents:
                content_type = doc.content_type or "unknown"
                length_bucket = get_length_bucket(doc.source_text_char_len)

                # Get gold spans for this document
                gold_spans = self.store.get_spans_for_document(doc.source_text_hash)
                claim_bearing_count = sum(1 for g in gold_spans if g.is_claim_bearing)

                # Get extracted spans for this document
                doc_extracted = [s for s in fixture.spans if s.document_id == doc.document_id]
                extracted_count = len(doc_extracted)

                # Find matches for this document
                adjusted_extracted = [
                    LoadedSpan(
                        claim_id=s.claim_id,
                        document_id=doc.source_text_hash,
                        text=s.text,
                        char_offset=s.char_offset,
                        char_length=s.char_length,
                        extraction_fidelity=s.extraction_fidelity,
                        match_method=s.match_method,
                        source_assertion_opinion=s.source_assertion_opinion,
                        claimset_orientation=s.claimset_orientation,
                        relevance_score=s.relevance_score,
                        verbatim_span=s.verbatim_span,
                    )
                    for s in doc_extracted
                ]

                matches, _, _ = find_span_matches(gold_spans, adjusted_extracted, self.iou_threshold)
                matched_claim_bearing = sum(1 for m in matches if m.gold_span.is_claim_bearing)

                # Update breakouts
                for breakout, key in [
                    (by_content_type, content_type),
                    (by_length_bucket, length_bucket),
                    (by_capture_mode, fixture.capture_mode),
                ]:
                    breakout[key].total_extracted += extracted_count
                    breakout[key].total_gold_claim_bearing += claim_bearing_count
                    breakout[key].matched_claim_bearing += matched_claim_bearing

        # Count total gold spans
        counts = self.store.count_records()
        report.gold_spans_total = counts.get("gold_span", 0)
        report.extracted_spans_total = all_fidelity.total_spans

        # Set final metrics
        report.extraction = all_extraction
        report.fidelity = all_fidelity
        report.by_content_type = dict(by_content_type)
        report.by_length_bucket = dict(by_length_bucket)
        report.by_capture_mode = dict(by_capture_mode)

        # Compute retrieval metrics from judgments
        claims = self.store.list_claims()
        report.coverage.total_claims = len(claims)

        total_retrieved = 0
        total_relevant = 0
        total_relevant_retrieved = 0

        for claim in claims:
            retrieval = self.score_claim_retrieval(claim.claim_id)
            report.per_claim_retrieval[claim.claim_id] = retrieval

            total_retrieved += retrieval.total_retrieved
            total_relevant += retrieval.total_relevant
            total_relevant_retrieved += retrieval.relevant_retrieved

            if retrieval.relevant_retrieved > 0:
                report.coverage.claims_with_germane_doc += 1

        report.retrieval = RetrievalMetrics(
            total_retrieved=total_retrieved,
            total_relevant=total_relevant,
            relevant_retrieved=total_relevant_retrieved,
        )

        # Compute coverage metrics from document annotations
        from .database import session_scope
        from .models import DocumentAnnotationModel
        from sqlalchemy import select, func

        with session_scope() as session:
            total_docs = session.execute(
                select(func.count()).select_from(DocumentAnnotationModel)
            ).scalar() or 0
            report.coverage.total_documents = total_docs

            lost_evidence = session.execute(
                select(func.count()).select_from(DocumentAnnotationModel).where(
                    DocumentAnnotationModel.lost_evidence_flag.is_(True)
                )
            ).scalar() or 0
            report.coverage.lost_evidence_documents = lost_evidence

        return report

    def export_json(self, report: ScorerReport, output_path: Path) -> None:
        """Export report to JSON."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(report.to_dict(), f, indent=2)

    def export_html(self, report: ScorerReport, output_path: Path) -> None:
        """Export report to HTML."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        data = report.to_dict()

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DB8R Eval Utility - Scorer Report</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 40px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }}
        h2 {{ color: #555; margin-top: 30px; }}
        .card {{ background: white; border-radius: 8px; padding: 20px; margin: 15px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .metric {{ display: inline-block; margin: 10px 20px 10px 0; }}
        .metric-value {{ font-size: 28px; font-weight: bold; color: #007bff; }}
        .metric-label {{ font-size: 14px; color: #666; }}
        table {{ border-collapse: collapse; width: 100%; margin-top: 15px; }}
        th, td {{ border: 1px solid #ddd; padding: 10px; text-align: left; }}
        th {{ background: #f8f9fa; }}
        tr:nth-child(even) {{ background: #f8f9fa; }}
        .good {{ color: #28a745; }}
        .warning {{ color: #ffc107; }}
        .bad {{ color: #dc3545; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>DB8R Eval Utility - v1 Metrics Report</h1>

        <div class="card">
            <h2>Summary</h2>
            <div class="metric">
                <div class="metric-value">{data['summary']['fixtures_evaluated']}</div>
                <div class="metric-label">Fixtures Evaluated</div>
            </div>
            <div class="metric">
                <div class="metric-value">{data['summary']['fixtures_skipped_partial']}</div>
                <div class="metric-label">Skipped (Partial)</div>
            </div>
            <div class="metric">
                <div class="metric-value">{data['summary']['gold_spans_total']}</div>
                <div class="metric-label">Gold Spans</div>
            </div>
            <div class="metric">
                <div class="metric-value">{data['summary']['extracted_spans_total']}</div>
                <div class="metric-label">Extracted Spans</div>
            </div>
        </div>

        <div class="card">
            <h2>Extraction Metrics</h2>
            <div class="metric">
                <div class="metric-value">{data['extraction']['well_formedness_precision']:.1%}</div>
                <div class="metric-label">Well-formedness Precision</div>
            </div>
            <div class="metric">
                <div class="metric-value">{data['extraction']['well_formed_recall']:.1%}</div>
                <div class="metric-label">Well-formed Recall</div>
            </div>
            <div class="metric">
                <div class="metric-value">{data['extraction']['targeting_precision']:.1%}</div>
                <div class="metric-label">Targeting Precision</div>
            </div>
            <div class="metric">
                <div class="metric-value">{data['extraction']['germane_recall']:.1%}</div>
                <div class="metric-label">Germane Recall</div>
            </div>
            <div class="metric">
                <div class="metric-value">{data['extraction']['f1_germane']:.1%}</div>
                <div class="metric-label">F1 (Germane)</div>
            </div>
        </div>

        <div class="card">
            <h2>Fidelity Metrics</h2>
            <div class="metric">
                <div class="metric-value">{data['fidelity']['mean_extraction_fidelity']:.1%}</div>
                <div class="metric-label">Mean Extraction Fidelity</div>
            </div>
            <div class="metric">
                <div class="metric-value">{data['fidelity']['verbatim_locatability_rate']:.1%}</div>
                <div class="metric-label">Verbatim Locatability</div>
            </div>
            <h3>Match Method Distribution</h3>
            <table>
                <tr><th>Method</th><th>Percentage</th></tr>
                {"".join(f"<tr><td>{m}</td><td>{p:.1%}</td></tr>" for m, p in data['fidelity']['match_method_distribution'].items())}
            </table>
        </div>

        <div class="card">
            <h2>Coverage Metrics</h2>
            <div class="metric">
                <div class="metric-value">{data['coverage']['lost_evidence_rate']:.1%}</div>
                <div class="metric-label">Lost Evidence Rate</div>
            </div>
            <div class="metric">
                <div class="metric-value">{data['coverage']['claim_coverage']:.1%}</div>
                <div class="metric-label">Claim Coverage</div>
            </div>
            <div class="metric">
                <div class="metric-value">{data['coverage']['primary_source_coverage']:.1%}</div>
                <div class="metric-label">Primary Source Coverage</div>
            </div>
        </div>

        <div class="card">
            <h2>Retrieval Metrics</h2>
            <div class="metric">
                <div class="metric-value">{data['retrieval']['recall']:.1%}</div>
                <div class="metric-label">Overall Recall</div>
            </div>
            <div class="metric">
                <div class="metric-value">{data['retrieval']['precision']:.1%}</div>
                <div class="metric-label">Overall Precision</div>
            </div>
        </div>

        <div class="card">
            <h2>Breakouts by Content Type</h2>
            <table>
                <tr><th>Content Type</th><th>Extracted</th><th>Gold</th><th>Precision</th><th>Recall</th></tr>
                {"".join(f"<tr><td>{ct}</td><td>{m['total_extracted']}</td><td>{m['total_gold']}</td><td>{m['well_formedness_precision']:.1%}</td><td>{m['well_formed_recall']:.1%}</td></tr>" for ct, m in data['breakouts']['by_content_type'].items())}
            </table>
        </div>

        <div class="card">
            <h2>Breakouts by Document Length</h2>
            <table>
                <tr><th>Length Bucket</th><th>Extracted</th><th>Gold</th><th>Precision</th><th>Recall</th></tr>
                {"".join(f"<tr><td>{lb}</td><td>{m['total_extracted']}</td><td>{m['total_gold']}</td><td>{m['well_formedness_precision']:.1%}</td><td>{m['well_formed_recall']:.1%}</td></tr>" for lb, m in data['breakouts']['by_length_bucket'].items())}
            </table>
        </div>

        <div class="card">
            <h2>Breakouts by Capture Mode</h2>
            <table>
                <tr><th>Capture Mode</th><th>Extracted</th><th>Gold</th><th>Precision</th><th>Recall</th></tr>
                {"".join(f"<tr><td>{cm}</td><td>{m['total_extracted']}</td><td>{m['total_gold']}</td><td>{m['well_formedness_precision']:.1%}</td><td>{m['well_formed_recall']:.1%}</td></tr>" for cm, m in data['breakouts']['by_capture_mode'].items())}
            </table>
        </div>
    </div>
</body>
</html>
"""
        with open(output_path, "w") as f:
            f.write(html)
