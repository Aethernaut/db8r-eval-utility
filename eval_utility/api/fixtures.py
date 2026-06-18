"""Fixture endpoints (read-only)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query

from ..fixtures import FixtureIntegrityError, list_fixtures, load_fixture
from .dependencies import get_fixtures_dir
from .schemas import (
    ExtractionStatusResponse,
    FixtureDetailResponse,
    FixtureDocumentDetailResponse,
    FixtureDocumentResponse,
    FixtureListResponse,
    FixtureRetrievalResultResponse,
    FixtureSpanResponse,
    FixtureSummaryResponse,
)

router = APIRouter()


def _extraction_status_to_response(status) -> ExtractionStatusResponse | None:
    """Convert LoadedExtractionStatus to response model."""
    if status is None:
        return None
    return ExtractionStatusResponse(
        partial_extraction=status.partial_extraction,
        chunks_processed=status.chunks_processed,
        chunks_total=status.chunks_total,
        tokens_used=status.tokens_used,
        token_budget=status.token_budget,
        warnings=status.warnings,
    )


def _document_to_response(doc, include_source_text: bool = False):
    """Convert LoadedDocument to response model."""
    base = {
        "document_id": doc.document_id,
        "source_url": doc.source_url,
        "source_title": doc.source_title,
        "source_domain": doc.source_domain,
        "provider": doc.provider,
        "content_type": doc.content_type,
        "fetched_at": doc.fetched_at,
        "source_reliability": doc.source_reliability,
        "retrieval_rank": doc.retrieval_rank,
        "source_text_hash": doc.source_text_hash,
        "source_text_char_len": doc.source_text_char_len,
        "extraction_status": _extraction_status_to_response(doc.extraction_status),
        "validation_warnings": doc.validation_warnings,
    }
    if include_source_text:
        return FixtureDocumentDetailResponse(source_text=doc.source_text, **base)
    return FixtureDocumentResponse(**base)


def _span_to_response(span) -> FixtureSpanResponse:
    """Convert LoadedSpan to response model."""
    return FixtureSpanResponse(
        claim_id=span.claim_id,
        document_id=span.document_id,
        text=span.text,
        char_offset=span.char_offset,
        char_length=span.char_length,
        extraction_fidelity=span.extraction_fidelity,
        match_method=span.match_method,
        source_assertion_opinion=span.source_assertion_opinion,
        claimset_orientation=span.claimset_orientation,
        relevance_score=span.relevance_score,
        verbatim_span=span.verbatim_span,
    )


def _retrieval_result_to_response(result) -> FixtureRetrievalResultResponse:
    """Convert LoadedRetrievalResult to response model."""
    return FixtureRetrievalResultResponse(
        document_id=result.document_id,
        url=result.url,
        title=result.title,
        rank=result.rank,
        provider=result.provider,
        relevance_score=result.relevance_score,
        status=result.status,
        error=result.error,
    )


@router.get("", response_model=FixtureListResponse)
def list_all_fixtures(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    fixtures_dir: Path = Depends(get_fixtures_dir),
) -> FixtureListResponse:
    """List fixtures (paginated)."""
    fixture_paths = list_fixtures(fixtures_dir)
    total = len(fixture_paths)

    # Paginate
    paginated_paths = fixture_paths[offset : offset + limit]

    fixtures = []
    for path in paginated_paths:
        try:
            fixture = load_fixture(path, verify_hashes=False, verify_spans=False)
            fixtures.append(
                FixtureSummaryResponse(
                    fixture_id=fixture.fixture_id,
                    capture_mode=fixture.capture_mode,
                    query=fixture.query,
                    job_id=fixture.job_id,
                    claimcheck_version=fixture.claimcheck_version,
                    captured_at=fixture.captured_at,
                    schema_version=fixture.schema_version,
                    document_count=len(fixture.documents),
                    span_count=len(fixture.spans),
                    retrieval_result_count=len(fixture.retrieval_results),
                    has_partial_extraction=fixture.has_partial_extraction(),
                    forage_strategy_id=fixture.forage_strategy_id,
                    forage_query_id=fixture.forage_query_id,
                )
            )
        except (FixtureIntegrityError, Exception):
            # Skip fixtures that fail to load in listing
            continue

    return FixtureListResponse(fixtures=fixtures, total=total)


@router.get("/{fixture_id}", response_model=FixtureDetailResponse)
def get_fixture(
    fixture_id: str,
    fixtures_dir: Path = Depends(get_fixtures_dir),
) -> FixtureDetailResponse:
    """Get fixture with documents, spans, retrieval_results."""
    fixture_path = fixtures_dir / f"{fixture_id}.json"
    if not fixture_path.exists():
        raise HTTPException(status_code=404, detail=f"Fixture {fixture_id} not found")

    try:
        fixture = load_fixture(fixture_path, verify_hashes=True, verify_spans=True)
    except FixtureIntegrityError as e:
        raise HTTPException(status_code=500, detail=f"Fixture integrity error: {e}")

    return FixtureDetailResponse(
        fixture_id=fixture.fixture_id,
        capture_mode=fixture.capture_mode,
        query=fixture.query,
        job_id=fixture.job_id,
        claimcheck_version=fixture.claimcheck_version,
        captured_at=fixture.captured_at,
        schema_version=fixture.schema_version,
        extraction_status=_extraction_status_to_response(fixture.extraction_status),
        forage_strategy_id=fixture.forage_strategy_id,
        forage_query_id=fixture.forage_query_id,
        documents=[_document_to_response(d) for d in fixture.documents],
        spans=[_span_to_response(s) for s in fixture.spans],
        retrieval_results=[_retrieval_result_to_response(r) for r in fixture.retrieval_results],
    )


@router.get("/{fixture_id}/documents/{doc_id}", response_model=FixtureDocumentDetailResponse)
def get_fixture_document(
    fixture_id: str,
    doc_id: str,
    fixtures_dir: Path = Depends(get_fixtures_dir),
) -> FixtureDocumentDetailResponse:
    """Get single document with source_text.

    doc_id can be either the document_id or source_text_hash.
    """
    fixture_path = fixtures_dir / f"{fixture_id}.json"
    if not fixture_path.exists():
        raise HTTPException(status_code=404, detail=f"Fixture {fixture_id} not found")

    try:
        fixture = load_fixture(fixture_path, verify_hashes=True, verify_spans=False)
    except FixtureIntegrityError as e:
        raise HTTPException(status_code=500, detail=f"Fixture integrity error: {e}")

    # Try to find document by ID first, then by hash
    doc = fixture.get_document(doc_id)
    if doc is None:
        doc = fixture.get_document_by_hash(doc_id)

    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found in fixture")

    return _document_to_response(doc, include_source_text=True)
