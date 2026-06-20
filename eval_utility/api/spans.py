"""Gold span CRUD endpoints + prefill."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from ..fixtures import FixtureIntegrityError, load_fixture
from ..store import GoldSpan, GoldStore
from .dependencies import get_fixtures_dir, get_store
from .schemas import (
    GoldSpanCreate,
    GoldSpanListResponse,
    GoldSpanResponse,
    GoldSpanUpdate,
    SpanPrefillRequest,
    SpanPrefillResponse,
)

router = APIRouter()


def _span_to_response(span: GoldSpan) -> GoldSpanResponse:
    """Convert GoldSpan to response model."""
    return GoldSpanResponse(
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
        created_at=span.created_at,
        updated_at=span.updated_at,
    )


@router.get("", response_model=GoldSpanListResponse)
def list_spans(
    document_id: str | None = Query(None),
    is_claim_bearing: bool | None = Query(None),
    label_source: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    store: GoldStore = Depends(get_store),
) -> GoldSpanListResponse:
    """List gold spans (filter by document_id, is_claim_bearing, label_source)."""
    from sqlalchemy import func, select

    from ..database import session_scope
    from ..models import GoldSpanModel

    with session_scope() as session:
        stmt = select(GoldSpanModel)
        count_stmt = select(func.count()).select_from(GoldSpanModel)

        if document_id is not None:
            stmt = stmt.where(GoldSpanModel.document_id == document_id)
            count_stmt = count_stmt.where(GoldSpanModel.document_id == document_id)

        if is_claim_bearing is not None:
            stmt = stmt.where(GoldSpanModel.is_claim_bearing == is_claim_bearing)
            count_stmt = count_stmt.where(GoldSpanModel.is_claim_bearing == is_claim_bearing)

        if label_source is not None:
            stmt = stmt.where(GoldSpanModel.label_source == label_source)
            count_stmt = count_stmt.where(GoldSpanModel.label_source == label_source)

        stmt = stmt.order_by(GoldSpanModel.document_id, GoldSpanModel.char_offset)
        stmt = stmt.offset(offset).limit(limit)

        models = session.execute(stmt).scalars().all()
        total = session.execute(count_stmt).scalar() or 0

    spans = []
    for m in models:
        span = GoldSpan(
            span_id=m.span_id,
            document_id=m.document_id,
            fixture_id=m.fixture_id,
            char_offset=m.char_offset,
            char_length=m.char_length,
            text=m.text,
            is_claim_bearing=m.is_claim_bearing,
            label_source=m.label_source,
            annotator_id=m.annotator_id,
            notes=m.notes,
            created_at=m.created_at.isoformat() if m.created_at else "",
            updated_at=m.updated_at.isoformat() if m.updated_at else "",
        )
        spans.append(_span_to_response(span))

    return GoldSpanListResponse(spans=spans, total=total)


@router.post("", response_model=GoldSpanResponse, status_code=201)
def create_span(
    data: GoldSpanCreate,
    store: GoldStore = Depends(get_store),
) -> GoldSpanResponse:
    """Create a gold span."""
    span = GoldSpan(
        span_id=f"span-{uuid.uuid4().hex[:12]}",
        document_id=data.document_id,
        fixture_id=data.fixture_id,
        char_offset=data.char_offset,
        char_length=data.char_length,
        text=data.text,
        is_claim_bearing=data.is_claim_bearing,
        label_source=data.label_source.value if data.label_source else None,
        annotator_id=data.annotator_id,
        notes=data.notes,
    )
    span = store.upsert_gold_span(span)
    return _span_to_response(span)


@router.get("/{span_id}", response_model=GoldSpanResponse)
def get_span(
    span_id: str,
    store: GoldStore = Depends(get_store),
) -> GoldSpanResponse:
    """Get a gold span."""
    span = store.get_gold_span(span_id)
    if span is None:
        raise HTTPException(status_code=404, detail=f"Span {span_id} not found")
    return _span_to_response(span)


@router.put("/{span_id}", response_model=GoldSpanResponse)
def update_span(
    span_id: str,
    data: GoldSpanUpdate,
    store: GoldStore = Depends(get_store),
) -> GoldSpanResponse:
    """Update a gold span (is_claim_bearing, label_source)."""
    span = store.get_gold_span(span_id)
    if span is None:
        raise HTTPException(status_code=404, detail=f"Span {span_id} not found")

    # Apply updates
    if data.is_claim_bearing is not None:
        span.is_claim_bearing = data.is_claim_bearing
    if data.label_source is not None:
        span.label_source = data.label_source.value
    if data.annotator_id is not None:
        span.annotator_id = data.annotator_id
    if data.notes is not None:
        span.notes = data.notes

    span = store.upsert_gold_span(span)
    return _span_to_response(span)


@router.delete("/{span_id}", status_code=204)
def delete_span(
    span_id: str,
    store: GoldStore = Depends(get_store),
) -> Response:
    """Delete a gold span."""
    span = store.get_gold_span(span_id)
    if span is None:
        raise HTTPException(status_code=404, detail=f"Span {span_id} not found")

    deleted = store.delete_gold_span(span_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Span {span_id} not found")

    return Response(status_code=204)


@router.post("/prefill", response_model=SpanPrefillResponse)
def prefill_spans(
    data: SpanPrefillRequest,
    store: GoldStore = Depends(get_store),
    fixtures_dir: Path = Depends(get_fixtures_dir),
) -> SpanPrefillResponse:
    """Import fixture spans as GoldSpan candidates.

    Loads fixture, finds document by hash, creates GoldSpan for each fixture span
    with is_claim_bearing=null (to be annotated). Skips duplicates unless
    overwrite_existing=true.
    """
    fixture_path = fixtures_dir / f"{data.fixture_id}.json"
    if not fixture_path.exists():
        raise HTTPException(status_code=404, detail=f"Fixture {data.fixture_id} not found")

    try:
        fixture = load_fixture(fixture_path, verify_hashes=True, verify_spans=False)
    except FixtureIntegrityError as e:
        raise HTTPException(status_code=500, detail=f"Fixture integrity error: {e}")

    # Find document by hash
    doc = fixture.get_document_by_hash(data.document_id)
    if doc is None:
        # Try by document_id
        doc = fixture.get_document(data.document_id)
        if doc is None:
            raise HTTPException(
                status_code=404,
                detail=f"Document {data.document_id} not found in fixture",
            )

    # Get fixture spans for this document
    fixture_spans = fixture.get_spans_for_document(doc.document_id)
    if not fixture_spans:
        return SpanPrefillResponse(created_count=0, skipped_count=0, spans=[])

    # Get existing spans for deduplication
    existing_spans = store.get_spans_for_document(doc.source_text_hash)
    existing_offsets = {(s.char_offset, s.char_length) for s in existing_spans}

    created_spans = []
    created_count = 0
    skipped_count = 0

    for fspan in fixture_spans:
        offset_key = (fspan.char_offset, fspan.char_length)

        # Skip if already exists (unless overwrite)
        if offset_key in existing_offsets and not data.overwrite_existing:
            skipped_count += 1
            continue

        # Use verbatim_span if available, otherwise use text
        span_text = fspan.verbatim_span if fspan.verbatim_span else fspan.text

        span = GoldSpan(
            span_id=f"span-{uuid.uuid4().hex[:12]}",
            document_id=doc.source_text_hash,  # Use content-addressed hash
            fixture_id=data.fixture_id,
            char_offset=fspan.char_offset,
            char_length=fspan.char_length,
            text=span_text,
            is_claim_bearing=None,  # To be annotated
            label_source=data.label_source.value,
            annotator_id=None,
            notes=None,
        )
        span = store.upsert_gold_span(span)
        created_spans.append(span)
        created_count += 1

    return SpanPrefillResponse(
        created_count=created_count,
        skipped_count=skipped_count,
        spans=[_span_to_response(s) for s in created_spans],
    )
