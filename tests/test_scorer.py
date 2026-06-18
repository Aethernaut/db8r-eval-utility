"""Tests for the scorer module."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from eval_utility.fixtures import LoadedSpan
from eval_utility.scorer import (
    ExtractionMetrics,
    FidelityMetrics,
    RetrievalMetrics,
    Scorer,
    char_range_iou,
    compute_retrieval_at_k,
    find_span_matches,
    get_length_bucket,
)
from eval_utility.store import Claim, GoldSpan, GoldStore, RetrievalJudgment


# --- char_range_iou tests ---


def test_char_range_iou_exact_match():
    assert char_range_iou(0, 10, 0, 10) == 1.0


def test_char_range_iou_disjoint():
    assert char_range_iou(0, 10, 20, 10) == 0.0


def test_char_range_iou_half_overlap():
    # ranges [0,10) and [5,15): intersection 5, union 15
    assert abs(char_range_iou(0, 10, 5, 10) - (5 / 15)) < 1e-9


def test_char_range_iou_meets_default_threshold():
    # [0,10) vs [0,12): inter 10, union 12 -> 0.833 >= 0.5
    assert char_range_iou(0, 10, 0, 12) >= 0.5


def test_char_range_iou_contained():
    # [0,20) contains [5,10): inter 5, union 20
    assert abs(char_range_iou(0, 20, 5, 5) - (5 / 20)) < 1e-9


def test_char_range_iou_zero_length():
    # Zero-length ranges
    assert char_range_iou(0, 0, 0, 0) == 0.0
    assert char_range_iou(0, 10, 5, 0) == 0.0


# --- get_length_bucket tests ---


def test_length_bucket_short():
    assert get_length_bucket(1000) == "short (<5k)"
    assert get_length_bucket(4999) == "short (<5k)"


def test_length_bucket_medium():
    assert get_length_bucket(5000) == "medium (5k-20k)"
    assert get_length_bucket(19999) == "medium (5k-20k)"


def test_length_bucket_long():
    assert get_length_bucket(20000) == "long (20k-50k)"
    assert get_length_bucket(49999) == "long (20k-50k)"


def test_length_bucket_very_long():
    assert get_length_bucket(50000) == "very_long (50k+)"
    assert get_length_bucket(100000) == "very_long (50k+)"


# --- find_span_matches tests ---


def test_find_span_matches_exact():
    """Test exact span matching."""
    gold = [
        GoldSpan(
            span_id="g1",
            document_id="doc1",
            fixture_id="fix1",
            char_offset=0,
            char_length=10,
            text="0123456789",
        )
    ]
    extracted = [
        LoadedSpan(
            claim_id="c1",
            document_id="doc1",
            text="0123456789",
            char_offset=0,
            char_length=10,
        )
    ]

    matches, unmatched_gold, unmatched_ext = find_span_matches(gold, extracted, 0.5)

    assert len(matches) == 1
    assert matches[0].iou == 1.0
    assert len(unmatched_gold) == 0
    assert len(unmatched_ext) == 0


def test_find_span_matches_no_match_different_doc():
    """Test that spans in different documents don't match."""
    gold = [
        GoldSpan(
            span_id="g1",
            document_id="doc1",
            fixture_id="fix1",
            char_offset=0,
            char_length=10,
            text="0123456789",
        )
    ]
    extracted = [
        LoadedSpan(
            claim_id="c1",
            document_id="doc2",  # Different document
            text="0123456789",
            char_offset=0,
            char_length=10,
        )
    ]

    matches, unmatched_gold, unmatched_ext = find_span_matches(gold, extracted, 0.5)

    assert len(matches) == 0
    assert len(unmatched_gold) == 1
    assert len(unmatched_ext) == 1


def test_find_span_matches_below_threshold():
    """Test that low-IoU matches are rejected."""
    gold = [
        GoldSpan(
            span_id="g1",
            document_id="doc1",
            fixture_id="fix1",
            char_offset=0,
            char_length=10,
            text="0123456789",
        )
    ]
    extracted = [
        LoadedSpan(
            claim_id="c1",
            document_id="doc1",
            text="89012345678901234567",
            char_offset=8,  # Only 2 chars overlap with [0,10)
            char_length=20,
        )
    ]

    # IoU = 2 / 28 ≈ 0.07 < 0.5
    matches, unmatched_gold, unmatched_ext = find_span_matches(gold, extracted, 0.5)

    assert len(matches) == 0
    assert len(unmatched_gold) == 1
    assert len(unmatched_ext) == 1


def test_find_span_matches_multiple():
    """Test matching with multiple spans."""
    gold = [
        GoldSpan(span_id="g1", document_id="doc1", fixture_id="fix1", char_offset=0, char_length=10, text="span1"),
        GoldSpan(span_id="g2", document_id="doc1", fixture_id="fix1", char_offset=20, char_length=10, text="span2"),
        GoldSpan(span_id="g3", document_id="doc1", fixture_id="fix1", char_offset=40, char_length=10, text="span3"),
    ]
    extracted = [
        LoadedSpan(claim_id="c1", document_id="doc1", text="span1", char_offset=0, char_length=10),
        LoadedSpan(claim_id="c1", document_id="doc1", text="span2", char_offset=20, char_length=10),
        # Missing span3
    ]

    matches, unmatched_gold, unmatched_ext = find_span_matches(gold, extracted, 0.5)

    assert len(matches) == 2
    assert len(unmatched_gold) == 1  # g3 not matched
    assert len(unmatched_ext) == 0


# --- compute_retrieval_at_k tests ---


def test_retrieval_at_k_perfect():
    """Test perfect retrieval."""
    retrieved = ["d1", "d2", "d3", "d4", "d5"]
    relevant = {"d1", "d2", "d3"}

    metrics = compute_retrieval_at_k(retrieved, relevant, k_values=[1, 3, 5])

    assert metrics.recall_at_k[3] == 1.0  # All 3 relevant found by k=3
    assert metrics.precision_at_k[3] == 1.0  # 3/3
    assert metrics.precision_at_k[5] == 0.6  # 3/5


def test_retrieval_at_k_partial():
    """Test partial retrieval."""
    retrieved = ["d1", "d4", "d5"]  # Only d1 is relevant
    relevant = {"d1", "d2", "d3"}

    metrics = compute_retrieval_at_k(retrieved, relevant, k_values=[1, 3])

    assert metrics.recall_at_k[1] == 1 / 3  # 1 of 3 relevant found
    assert metrics.precision_at_k[1] == 1.0  # 1/1
    assert metrics.recall_at_k[3] == 1 / 3  # Still only 1 found
    assert abs(metrics.precision_at_k[3] - 1 / 3) < 1e-9  # 1/3


def test_retrieval_at_k_empty_relevant():
    """Test with no relevant documents."""
    retrieved = ["d1", "d2", "d3"]
    relevant: set[str] = set()

    metrics = compute_retrieval_at_k(retrieved, relevant, k_values=[1, 3])

    assert metrics.recall_at_k[1] == 0.0
    assert metrics.recall_at_k[3] == 0.0


# --- ExtractionMetrics tests ---


def test_extraction_metrics_precision():
    metrics = ExtractionMetrics(
        total_extracted=10,
        matched_claim_bearing=7,
        matched_relevant=5,
    )

    assert metrics.well_formedness_precision == 0.7
    assert metrics.targeting_precision == 0.5


def test_extraction_metrics_recall():
    metrics = ExtractionMetrics(
        total_gold_claim_bearing=10,
        total_gold_relevant=8,
        matched_claim_bearing=6,
        matched_relevant=4,
    )

    assert metrics.well_formed_recall == 0.6
    assert metrics.germane_recall == 0.5


def test_extraction_metrics_f1():
    metrics = ExtractionMetrics(
        total_extracted=10,
        total_gold_relevant=10,
        matched_relevant=5,
    )

    # Precision = 5/10 = 0.5, Recall = 5/10 = 0.5, F1 = 0.5
    assert metrics.f1_germane == 0.5


def test_extraction_metrics_zero_division():
    metrics = ExtractionMetrics()

    assert metrics.well_formedness_precision == 0.0
    assert metrics.targeting_precision == 0.0
    assert metrics.well_formed_recall == 0.0
    assert metrics.germane_recall == 0.0
    assert metrics.f1_germane == 0.0


# --- FidelityMetrics tests ---


def test_fidelity_metrics_distribution():
    metrics = FidelityMetrics(
        match_method_counts={"exact": 80, "normalized": 15, "fuzzy": 5},
        total_spans=100,
    )

    dist = metrics.match_method_distribution
    assert dist["exact"] == 0.8
    assert dist["normalized"] == 0.15
    assert dist["fuzzy"] == 0.05


def test_fidelity_metrics_mean_fidelity():
    metrics = FidelityMetrics(
        extraction_fidelities=[1.0, 0.9, 0.8, 0.95],
    )

    assert abs(metrics.mean_extraction_fidelity - 0.9125) < 1e-9


def test_fidelity_metrics_verbatim_rate():
    metrics = FidelityMetrics(
        total_spans=100,
        verbatim_locatable=95,
    )

    assert metrics.verbatim_locatability_rate == 0.95


# --- RetrievalMetrics tests ---


def test_retrieval_metrics_properties():
    metrics = RetrievalMetrics(
        total_retrieved=20,
        total_relevant=10,
        relevant_retrieved=8,
    )

    assert metrics.recall == 0.8
    assert metrics.precision == 0.4


# --- Scorer integration tests ---


@pytest.fixture
def temp_dirs():
    """Create temporary directories."""
    with tempfile.TemporaryDirectory() as fixtures_dir:
        with tempfile.TemporaryDirectory() as gold_dir:
            yield Path(fixtures_dir), Path(gold_dir)


@pytest.fixture
def test_store(temp_dirs):
    """Create a test store."""
    _, gold_dir = temp_dirs
    db_path = gold_dir / "test_gold.db"
    return GoldStore(db_path=db_path)


@pytest.fixture
def test_fixture(temp_dirs):
    """Create a test fixture file."""
    fixtures_dir, _ = temp_dirs

    # Create fixture data
    import hashlib

    source_text = "This is the source text for testing span offsets and extraction."
    source_text_hash = hashlib.sha256(source_text.encode()).hexdigest()

    fixture_data = {
        "fixture_id": "fix-test123",
        "capture_mode": "search_A",
        "query": "test query",
        "job_id": "job-123",
        "claimcheck_version": "1.0.0",
        "captured_at": "2024-01-01T00:00:00Z",
        "schema_version": "fixture_v1",
        "documents": [
            {
                "document_id": "doc-001",
                "source_url": "https://example.com/article",
                "source_title": "Test Article",
                "source_domain": "example.com",
                "provider": "test_provider",
                "content_type": "text/html",
                "fetched_at": "2024-01-01T00:00:00Z",
                "source_reliability": 0.9,
                "retrieval_rank": 1,
                "source_text": source_text,
                "source_text_hash": source_text_hash,
                "source_text_char_len": len(source_text),
                "extraction_status": {
                    "partial_extraction": False,
                    "chunks_processed": 1,
                    "chunks_total": 1,
                    "tokens_used": 100,
                    "token_budget": 1000,
                    "warnings": [],
                },
                "validation_warnings": [],
            }
        ],
        "spans": [
            {
                "claim_id": "claim-001",
                "document_id": "doc-001",
                "text": "source text",
                "char_offset": 12,
                "char_length": 11,
                "extraction_fidelity": 0.95,
                "match_method": "exact",
                "verbatim_span": "source text",
            },
            {
                "claim_id": "claim-001",
                "document_id": "doc-001",
                "text": "testing span",
                "char_offset": 28,
                "char_length": 12,
                "extraction_fidelity": 0.90,
                "match_method": "normalized",
                "verbatim_span": "testing span",
            },
        ],
        "retrieval_results": [],
    }

    fixture_path = fixtures_dir / "fix-test123.json"
    with open(fixture_path, "w") as f:
        json.dump(fixture_data, f)

    return fixture_data, source_text_hash


def test_scorer_score_fixture(temp_dirs, test_store, test_fixture):
    """Test scoring a single fixture."""
    fixtures_dir, _ = temp_dirs
    fixture_data, source_text_hash = test_fixture

    # Add gold spans to the store
    gold_span = GoldSpan(
        span_id="gold-1",
        document_id=source_text_hash,
        fixture_id="fix-test123",
        char_offset=12,
        char_length=11,
        text="source text",
        is_claim_bearing=True,
    )
    test_store.upsert_gold_span(gold_span)

    # Create scorer
    from eval_utility.config import Settings

    settings = Settings(fixtures_dir=fixtures_dir)
    scorer = Scorer(store=test_store, settings=settings)

    # Load and score fixture
    from eval_utility.fixtures import load_fixture

    fixture = load_fixture(fixtures_dir / "fix-test123.json", verify_hashes=False, verify_spans=False)
    extraction, fidelity = scorer.score_fixture(fixture)

    # Check extraction metrics
    assert extraction.total_extracted == 2
    assert extraction.total_gold_claim_bearing == 1
    assert extraction.matched_claim_bearing == 1  # Exact match

    # Check fidelity metrics
    assert fidelity.total_spans == 2
    assert fidelity.match_method_counts["exact"] == 1
    assert fidelity.match_method_counts["normalized"] == 1
    assert len(fidelity.extraction_fidelities) == 2
    assert fidelity.verbatim_locatable == 2  # Both verbatim_spans found


def test_scorer_score_all_empty(temp_dirs, test_store):
    """Test scoring with no fixtures."""
    fixtures_dir, _ = temp_dirs

    from eval_utility.config import Settings

    settings = Settings(fixtures_dir=fixtures_dir)
    scorer = Scorer(store=test_store, settings=settings)

    report = scorer.score_all()

    assert report.fixtures_evaluated == 0
    assert report.extraction.total_extracted == 0


def test_scorer_score_claim_retrieval(temp_dirs, test_store):
    """Test scoring claim retrieval."""
    fixtures_dir, _ = temp_dirs

    # Create a claim
    claim = Claim(claim_id="claim-001", text="Test claim")
    test_store.upsert_claim(claim)

    # Create retrieval judgments
    judgments = [
        RetrievalJudgment(
            claim_id="claim-001",
            document_id="doc-001",
            relevant=1,
            retrieval_rank=1,
        ),
        RetrievalJudgment(
            claim_id="claim-001",
            document_id="doc-002",
            relevant=0,
            retrieval_rank=2,
        ),
        RetrievalJudgment(
            claim_id="claim-001",
            document_id="doc-003",
            relevant=1,
            retrieval_rank=3,
        ),
    ]
    for j in judgments:
        test_store.upsert_retrieval_judgment(j)

    from eval_utility.config import Settings

    settings = Settings(fixtures_dir=fixtures_dir)
    scorer = Scorer(store=test_store, settings=settings)

    metrics = scorer.score_claim_retrieval("claim-001")

    assert metrics.total_retrieved == 3
    assert metrics.total_relevant == 2
    assert metrics.relevant_retrieved == 2
    assert metrics.recall_at_k[1] == 0.5  # 1 of 2 relevant at k=1
    assert metrics.recall_at_k[3] == 1.0  # 2 of 2 relevant at k=3


def test_scorer_export_json(temp_dirs, test_store):
    """Test JSON export."""
    fixtures_dir, gold_dir = temp_dirs

    from eval_utility.config import Settings

    settings = Settings(fixtures_dir=fixtures_dir)
    scorer = Scorer(store=test_store, settings=settings)

    report = scorer.score_all()
    output_path = gold_dir / "report.json"
    scorer.export_json(report, output_path)

    assert output_path.exists()

    with open(output_path) as f:
        data = json.load(f)

    assert "summary" in data
    assert "extraction" in data
    assert "fidelity" in data
    assert "coverage" in data
    assert "retrieval" in data


def test_scorer_export_html(temp_dirs, test_store):
    """Test HTML export."""
    fixtures_dir, gold_dir = temp_dirs

    from eval_utility.config import Settings

    settings = Settings(fixtures_dir=fixtures_dir)
    scorer = Scorer(store=test_store, settings=settings)

    report = scorer.score_all()
    output_path = gold_dir / "report.html"
    scorer.export_html(report, output_path)

    assert output_path.exists()

    with open(output_path) as f:
        html = f.read()

    assert "DB8R Eval Utility" in html
    assert "Extraction Metrics" in html
    assert "Fidelity Metrics" in html


def test_scorer_skip_partial_extraction(temp_dirs, test_store):
    """Test that partial extraction fixtures are skipped."""
    fixtures_dir, _ = temp_dirs

    import hashlib

    source_text = "Test text"
    source_text_hash = hashlib.sha256(source_text.encode()).hexdigest()

    fixture_data = {
        "fixture_id": "fix-partial",
        "capture_mode": "search_A",
        "query": "test",
        "job_id": "job-1",
        "claimcheck_version": "1.0",
        "captured_at": "2024-01-01T00:00:00Z",
        "schema_version": "fixture_v1",
        "documents": [
            {
                "document_id": "doc-1",
                "source_url": "https://example.com",
                "source_title": "Test",
                "source_domain": "example.com",
                "provider": "test",
                "content_type": "text/html",
                "fetched_at": "2024-01-01T00:00:00Z",
                "source_reliability": 0.5,
                "retrieval_rank": 1,
                "source_text": source_text,
                "source_text_hash": source_text_hash,
                "source_text_char_len": len(source_text),
                "extraction_status": {
                    "partial_extraction": True,  # Partial!
                    "chunks_processed": 5,
                    "chunks_total": 10,
                    "tokens_used": 500,
                    "token_budget": 500,
                    "warnings": ["max_chunks_exceeded"],
                },
                "validation_warnings": [],
            }
        ],
        "spans": [],
        "retrieval_results": [],
    }

    fixture_path = fixtures_dir / "fix-partial.json"
    with open(fixture_path, "w") as f:
        json.dump(fixture_data, f)

    from eval_utility.config import Settings

    settings = Settings(fixtures_dir=fixtures_dir)
    scorer = Scorer(store=test_store, settings=settings)

    report = scorer.score_all(skip_partial=True)

    assert report.fixtures_evaluated == 0
    assert report.fixtures_skipped_partial == 1
