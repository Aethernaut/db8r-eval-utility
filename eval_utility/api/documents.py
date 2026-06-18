"""Document annotation endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..store import DocumentAnnotation, GoldSpan, GoldStore
from .dependencies import get_store
from .schemas import (
    DocumentAnnotationResponse,
    DocumentAnnotationUpdate,
    GoldSpanResponse,
)

router = APIRouter()


def _annotation_to_response(annotation: DocumentAnnotation) -> DocumentAnnotationResponse:
    """Convert DocumentAnnotation to response model."""
    return DocumentAnnotationResponse(
        document_id=annotation.document_id,
        fixture_id=annotation.fixture_id,
        exhaustively_annotated=annotation.exhaustively_annotated,
        lost_evidence_flag=annotation.lost_evidence_flag,
        lost_evidence_note=annotation.lost_evidence_note,
        annotator_id=annotation.annotator_id,
        created_at=annotation.created_at,
        updated_at=annotation.updated_at,
    )


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


@router.get("/{document_id}", response_model=DocumentAnnotationResponse)
def get_document_annotation(
    document_id: str,
    store: GoldStore = Depends(get_store),
) -> DocumentAnnotationResponse:
    """Get annotation for a document (by source_text_hash)."""
    annotation = store.get_document_annotation(document_id)
    if annotation is None:
        raise HTTPException(status_code=404, detail=f"Document annotation {document_id} not found")
    return _annotation_to_response(annotation)


@router.put("/{document_id}", response_model=DocumentAnnotationResponse)
def upsert_document_annotation(
    document_id: str,
    data: DocumentAnnotationUpdate,
    fixture_id: str | None = None,
    store: GoldStore = Depends(get_store),
) -> DocumentAnnotationResponse:
    """Upsert annotation for a document (exhaustively_annotated, lost_evidence_flag)."""
    # Get existing annotation or create new one
    existing = store.get_document_annotation(document_id)

    if existing:
        # Update existing
        if data.exhaustively_annotated is not None:
            existing.exhaustively_annotated = data.exhaustively_annotated
        if data.lost_evidence_flag is not None:
            existing.lost_evidence_flag = data.lost_evidence_flag
        if data.lost_evidence_note is not None:
            existing.lost_evidence_note = data.lost_evidence_note
        if data.annotator_id is not None:
            existing.annotator_id = data.annotator_id
        annotation = store.upsert_document_annotation(existing)
    else:
        # Create new - need fixture_id
        if fixture_id is None:
            raise HTTPException(
                status_code=400,
                detail="fixture_id is required when creating a new document annotation",
            )
        annotation = DocumentAnnotation(
            document_id=document_id,
            fixture_id=fixture_id,
            exhaustively_annotated=data.exhaustively_annotated or False,
            lost_evidence_flag=data.lost_evidence_flag or False,
            lost_evidence_note=data.lost_evidence_note,
            annotator_id=data.annotator_id,
        )
        annotation = store.upsert_document_annotation(annotation)

    return _annotation_to_response(annotation)


@router.get("/{document_id}/spans", response_model=list[GoldSpanResponse])
def list_document_spans(
    document_id: str,
    store: GoldStore = Depends(get_store),
) -> list[GoldSpanResponse]:
    """List gold spans for a document."""
    spans = store.get_spans_for_document(document_id)
    return [_span_to_response(s) for s in spans]
