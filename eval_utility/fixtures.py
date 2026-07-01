"""EU-3 — Fixture load/validate. Fixtures are immutable and hashed.

A fixture wraps a captured ClaimCheck SearchJobResponse plus integrity metadata.
Key invariants (README §2, §3):
  - `source_text_hash` pins the exact text gold offsets reference; never mutate a fixture.
  - Read span offsets from the response `claims[]` array only (projections carry null offsets).
  - Capture each document's `extraction_status` (CC-3a) so partial fixtures can be excluded
    from extraction-recall denominators.
  - Validate against `verbatim_span` for offset scoring (claim.statement may be normalized).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def source_text_hash(source_text: str) -> str:
    """Compute SHA-256 hash of source_text for content-addressing."""
    return hashlib.sha256(source_text.encode("utf-8")).hexdigest()


class FixtureIntegrityError(Exception):
    """Raised when fixture fails integrity checks."""

    pass


@dataclass
class LoadedExtractionStatus:
    """Extraction status from a loaded fixture."""

    partial_extraction: bool
    chunks_processed: int | None = None
    chunks_total: int | None = None
    tokens_used: int | None = None
    token_budget: int | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass
class LoadedDocument:
    """A document from a loaded fixture, with integrity-checked source_text."""

    document_id: str
    source_url: str
    source_title: str | None
    source_domain: str | None
    provider: str | None
    content_type: str | None
    fetched_at: str | None
    source_reliability: float | None
    retrieval_rank: int | None
    source_text: str
    source_text_hash: str
    source_text_char_len: int
    extraction_status: LoadedExtractionStatus | None = None
    validation_warnings: list[str] = field(default_factory=list)
    # CC-3: MBFC Source Reliability metadata
    publisher_name: str | None = None
    publisher_mbfc_key: str | None = None
    mbfc_factual_rating: str | None = None
    mbfc_bias_rating: str | None = None

    def verify_hash(self) -> bool:
        """Verify source_text_hash matches actual source_text."""
        return source_text_hash(self.source_text) == self.source_text_hash


@dataclass
class LoadedSpan:
    """An extracted span from a loaded fixture."""

    claim_id: str
    document_id: str
    text: str  # claim.statement — may be normalized
    char_offset: int
    char_length: int
    extraction_fidelity: float | None = None
    match_method: str | None = None
    source_assertion_opinion: dict[str, Any] | None = None
    claimset_orientation: str | None = None
    relevance_score: float | None = None
    verbatim_span: str | None = None  # CC-10a: exact source slice for scoring
    # CC-3: Claim Attribution metadata
    claim_attribution: dict[str, Any] | None = None
    claimant_name: str | None = None
    claimant_key: str | None = None
    attribution_type: str | None = None

    def verify_against_source(self, source_text: str) -> bool:
        """Verify verbatim_span matches source_text slice at offset."""
        if self.verbatim_span is None:
            return False
        extracted = source_text[self.char_offset : self.char_offset + self.char_length]
        return extracted == self.verbatim_span


@dataclass
class LoadedRetrievalResult:
    """A retrieval result from a loaded fixture."""

    document_id: str | None
    url: str
    title: str | None
    rank: int
    provider: str | None
    relevance_score: float | None
    status: str | None
    error: str | None = None


@dataclass
class LoadedFixture:
    """A loaded and validated fixture."""

    fixture_id: str
    capture_mode: str  # search_A | extract_B | debate_C
    query: str | None
    job_id: str | None
    claimcheck_version: str | None
    captured_at: str
    schema_version: str

    documents: list[LoadedDocument]
    spans: list[LoadedSpan]
    retrieval_results: list[LoadedRetrievalResult]

    extraction_status: LoadedExtractionStatus | None = None
    forage_strategy_id: str | None = None
    forage_query_id: str | None = None
    # CC-3: Search Target Contract
    search_target_preset: str | None = None
    target_metrics: dict[str, Any] | None = None

    # Indexed lookups (built on load)
    _documents_by_id: dict[str, LoadedDocument] = field(default_factory=dict, repr=False)
    _documents_by_hash: dict[str, LoadedDocument] = field(default_factory=dict, repr=False)
    _spans_by_document: dict[str, list[LoadedSpan]] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        """Build indexes for efficient lookup."""
        self._documents_by_id = {d.document_id: d for d in self.documents}
        self._documents_by_hash = {d.source_text_hash: d for d in self.documents}
        self._spans_by_document = {}
        for span in self.spans:
            self._spans_by_document.setdefault(span.document_id, []).append(span)

    def get_document(self, document_id: str) -> LoadedDocument | None:
        """Get document by ID."""
        return self._documents_by_id.get(document_id)

    def get_document_by_hash(self, source_text_hash: str) -> LoadedDocument | None:
        """Get document by content hash."""
        return self._documents_by_hash.get(source_text_hash)

    def get_spans_for_document(self, document_id: str) -> list[LoadedSpan]:
        """Get all spans for a document."""
        return self._spans_by_document.get(document_id, [])

    def has_partial_extraction(self) -> bool:
        """Check if any document has partial extraction."""
        for doc in self.documents:
            if doc.extraction_status and doc.extraction_status.partial_extraction:
                return True
        return False


def _parse_extraction_status(data: dict[str, Any] | None) -> LoadedExtractionStatus | None:
    """Parse extraction status from fixture data."""
    if not data:
        return None
    return LoadedExtractionStatus(
        partial_extraction=data.get("partial_extraction", False),
        chunks_processed=data.get("chunks_processed"),
        chunks_total=data.get("chunks_total"),
        tokens_used=data.get("tokens_used"),
        token_budget=data.get("token_budget"),
        warnings=data.get("warnings", []),
    )


def _parse_document(data: dict[str, Any]) -> LoadedDocument:
    """Parse a document from fixture data."""
    return LoadedDocument(
        document_id=data.get("document_id", ""),
        source_url=data.get("source_url", ""),
        source_title=data.get("source_title"),
        source_domain=data.get("source_domain"),
        provider=data.get("provider"),
        content_type=data.get("content_type"),
        fetched_at=data.get("fetched_at"),
        source_reliability=data.get("source_reliability"),
        retrieval_rank=data.get("retrieval_rank"),
        source_text=data.get("source_text", ""),
        source_text_hash=data.get("source_text_hash", ""),
        source_text_char_len=data.get("source_text_char_len", 0),
        extraction_status=_parse_extraction_status(data.get("extraction_status")),
        validation_warnings=data.get("validation_warnings", []),
        # CC-3: MBFC Source Reliability metadata
        publisher_name=data.get("publisher_name"),
        publisher_mbfc_key=data.get("publisher_mbfc_key"),
        mbfc_factual_rating=data.get("mbfc_factual_rating"),
        mbfc_bias_rating=data.get("mbfc_bias_rating"),
    )


def _parse_span(data: dict[str, Any]) -> LoadedSpan:
    """Parse a span from fixture data."""
    return LoadedSpan(
        claim_id=data.get("claim_id", ""),
        document_id=data.get("document_id", ""),
        text=data.get("text", ""),
        char_offset=data.get("char_offset", 0),
        char_length=data.get("char_length", 0),
        extraction_fidelity=data.get("extraction_fidelity"),
        match_method=data.get("match_method"),
        source_assertion_opinion=data.get("source_assertion_opinion"),
        claimset_orientation=data.get("claimset_orientation"),
        relevance_score=data.get("relevance_score"),
        verbatim_span=data.get("verbatim_span"),
        # CC-3: Claim Attribution metadata
        claim_attribution=data.get("claim_attribution"),
        claimant_name=data.get("claimant_name"),
        claimant_key=data.get("claimant_key"),
        attribution_type=data.get("attribution_type"),
    )


def _parse_retrieval_result(data: dict[str, Any]) -> LoadedRetrievalResult:
    """Parse a retrieval result from fixture data."""
    return LoadedRetrievalResult(
        document_id=data.get("document_id"),
        url=data.get("url", ""),
        title=data.get("title"),
        rank=data.get("rank", 0),
        provider=data.get("provider"),
        relevance_score=data.get("relevance_score"),
        status=data.get("status"),
        error=data.get("error"),
    )


def load_fixture(
    path: str | Path,
    *,
    verify_hashes: bool = True,
    verify_spans: bool = True,
) -> LoadedFixture:
    """Load and validate a fixture from disk.

    Args:
        path: Path to the fixture JSON file
        verify_hashes: If True, verify each document's source_text_hash
        verify_spans: If True, verify each span's verbatim_span against source_text

    Returns:
        LoadedFixture with all data and indexes built

    Raises:
        FixtureIntegrityError: If any integrity check fails
        FileNotFoundError: If the fixture file doesn't exist
        json.JSONDecodeError: If the file is not valid JSON
    """
    path = Path(path)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Parse documents
    documents = [_parse_document(d) for d in data.get("documents", [])]

    # Verify document hashes
    if verify_hashes:
        for doc in documents:
            if not doc.verify_hash():
                raise FixtureIntegrityError(
                    f"Document {doc.document_id} hash mismatch: "
                    f"stored={doc.source_text_hash[:16]}..., "
                    f"computed={source_text_hash(doc.source_text)[:16]}..."
                )

    # Parse spans
    spans = [_parse_span(s) for s in data.get("spans", [])]

    # Verify spans against source_text
    if verify_spans:
        doc_by_id = {d.document_id: d for d in documents}
        for span in spans:
            doc = doc_by_id.get(span.document_id)
            if doc and span.verbatim_span is not None:
                if not span.verify_against_source(doc.source_text):
                    extracted = doc.source_text[span.char_offset : span.char_offset + span.char_length]
                    raise FixtureIntegrityError(
                        f"Span {span.claim_id} verbatim mismatch: "
                        f"verbatim_span={span.verbatim_span!r}, "
                        f"source_text[{span.char_offset}:{span.char_offset + span.char_length}]={extracted!r}"
                    )

    # Parse retrieval results
    retrieval_results = [_parse_retrieval_result(r) for r in data.get("retrieval_results", [])]

    # CC-3: Parse search_target if present
    search_target = data.get("search_target") or {}
    search_target_preset = search_target.get("preset") if isinstance(search_target, dict) else None

    return LoadedFixture(
        fixture_id=data.get("fixture_id", ""),
        capture_mode=data.get("capture_mode", ""),
        query=data.get("query"),
        job_id=data.get("job_id"),
        claimcheck_version=data.get("claimcheck_version"),
        captured_at=data.get("captured_at", ""),
        schema_version=data.get("schema_version", ""),
        documents=documents,
        spans=spans,
        retrieval_results=retrieval_results,
        extraction_status=_parse_extraction_status(data.get("extraction_status")),
        forage_strategy_id=data.get("forage_strategy_id"),
        forage_query_id=data.get("forage_query_id"),
        # CC-3: Search Target Contract
        search_target_preset=search_target_preset or data.get("search_target_preset"),
        target_metrics=data.get("target_metrics"),
    )


def list_fixtures(fixtures_dir: str | Path) -> list[Path]:
    """List all fixture files in a directory."""
    fixtures_dir = Path(fixtures_dir)
    if not fixtures_dir.exists():
        return []
    return sorted(fixtures_dir.glob("fix-*.json"))


def load_all_fixtures(
    fixtures_dir: str | Path,
    *,
    verify_hashes: bool = True,
    verify_spans: bool = True,
    skip_errors: bool = False,
) -> list[LoadedFixture]:
    """Load all fixtures from a directory.

    Args:
        fixtures_dir: Directory containing fixture JSON files
        verify_hashes: If True, verify each document's source_text_hash
        verify_spans: If True, verify each span's verbatim_span
        skip_errors: If True, skip fixtures that fail to load instead of raising

    Returns:
        List of loaded fixtures
    """
    fixtures: list[LoadedFixture] = []
    for path in list_fixtures(fixtures_dir):
        try:
            fixture = load_fixture(path, verify_hashes=verify_hashes, verify_spans=verify_spans)
            fixtures.append(fixture)
        except Exception as e:
            if skip_errors:
                print(f"Warning: Failed to load {path}: {e}")
            else:
                raise
    return fixtures
