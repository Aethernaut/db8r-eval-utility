"""Evidence quality label endpoints (Foraging Learning).

These endpoints support collection of evidence quality assessments
that feed into the foraging learning pipeline:

Document-level labels:
  - relevance: germane / partially_germane / background / irrelevant
  - claim_relation: supports / contradicts / mixed / background / unclear
  - source_issues: paywall_partial, weak_attribution, stale_source, etc.
  - corroboration_status: independent / same_cluster / duplicate

Span-level labels:
  - extraction_quality: faithful / overbroad / underspecified / wrong / unsupported
  - grounding_quality: sufficient / missing_context / wrong_span / source_mismatch
  - evidence_usability: argument_support / rebuttal_support / context_only / unusable
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from ..store import DocumentQualityLabel, GoldStore, SpanQualityLabel
from .dependencies import get_store
from .schemas import (
    DocumentQualityLabelCreate,
    DocumentQualityLabelListResponse,
    DocumentQualityLabelResponse,
    DocumentQualityLabelUpdate,
    SpanQualityLabelCreate,
    SpanQualityLabelListResponse,
    SpanQualityLabelResponse,
    SpanQualityLabelUpdate,
)

router = APIRouter()


# --- Conversion helpers ---


def _doc_label_to_response(label: DocumentQualityLabel) -> DocumentQualityLabelResponse:
    return DocumentQualityLabelResponse(
        id=label.id,
        document_id=label.document_id,
        claim_id=label.claim_id,
        relevance=label.relevance,
        claim_relation=label.claim_relation,
        source_issues=label.source_issues,
        corroboration_status=label.corroboration_status,
        corroboration_cluster_id=label.corroboration_cluster_id,
        annotator_id=label.annotator_id,
        notes=label.notes,
        created_at=label.created_at,
        updated_at=label.updated_at,
    )


def _span_label_to_response(label: SpanQualityLabel) -> SpanQualityLabelResponse:
    return SpanQualityLabelResponse(
        id=label.id,
        span_id=label.span_id,
        extraction_quality=label.extraction_quality,
        grounding_quality=label.grounding_quality,
        evidence_usability=label.evidence_usability,
        annotator_id=label.annotator_id,
        notes=label.notes,
        created_at=label.created_at,
        updated_at=label.updated_at,
    )


# --- Document Quality Label endpoints ---


@router.post("/documents", response_model=DocumentQualityLabelResponse, status_code=201)
def create_document_quality_label(
    data: DocumentQualityLabelCreate,
    store: GoldStore = Depends(get_store),
) -> DocumentQualityLabelResponse:
    """Create a document quality label."""
    source_issues_strs = [si.value for si in data.source_issues] if data.source_issues else None

    label = store.create_document_quality_label(
        document_id=data.document_id,
        claim_id=data.claim_id,
        relevance=data.relevance.value if data.relevance else None,
        claim_relation=data.claim_relation.value if data.claim_relation else None,
        source_issues=source_issues_strs,
        corroboration_status=data.corroboration_status.value if data.corroboration_status else None,
        corroboration_cluster_id=data.corroboration_cluster_id,
        annotator_id=data.annotator_id,
        notes=data.notes,
    )
    return _doc_label_to_response(label)


@router.get("/documents", response_model=DocumentQualityLabelListResponse)
def list_document_quality_labels(
    document_id: str | None = Query(None),
    claim_id: str | None = Query(None),
    relevance: str | None = Query(None),
    corroboration_cluster_id: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    store: GoldStore = Depends(get_store),
) -> DocumentQualityLabelListResponse:
    """List document quality labels with optional filters."""
    labels, total = store.list_document_quality_labels(
        document_id=document_id,
        claim_id=claim_id,
        relevance=relevance,
        corroboration_cluster_id=corroboration_cluster_id,
        limit=limit,
        offset=offset,
    )
    return DocumentQualityLabelListResponse(
        labels=[_doc_label_to_response(label) for label in labels],
        total=total,
    )


@router.get("/documents/{label_id}", response_model=DocumentQualityLabelResponse)
def get_document_quality_label(
    label_id: str,
    store: GoldStore = Depends(get_store),
) -> DocumentQualityLabelResponse:
    """Get a document quality label by ID."""
    label = store.get_document_quality_label(label_id)
    if not label:
        raise HTTPException(status_code=404, detail="Document quality label not found")
    return _doc_label_to_response(label)


@router.put("/documents/{label_id}", response_model=DocumentQualityLabelResponse)
def update_document_quality_label(
    label_id: str,
    data: DocumentQualityLabelUpdate,
    store: GoldStore = Depends(get_store),
) -> DocumentQualityLabelResponse:
    """Update a document quality label."""
    existing = store.get_document_quality_label(label_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Document quality label not found")

    # Build updated label
    source_issues = existing.source_issues
    if data.source_issues is not None:
        source_issues = [si.value for si in data.source_issues]

    updated = DocumentQualityLabel(
        id=existing.id,
        document_id=existing.document_id,
        claim_id=existing.claim_id,
        relevance=data.relevance.value if data.relevance else existing.relevance,
        claim_relation=data.claim_relation.value if data.claim_relation else existing.claim_relation,
        source_issues=source_issues,
        corroboration_status=(
            data.corroboration_status.value if data.corroboration_status else existing.corroboration_status
        ),
        corroboration_cluster_id=(
            data.corroboration_cluster_id
            if data.corroboration_cluster_id is not None
            else existing.corroboration_cluster_id
        ),
        annotator_id=data.annotator_id if data.annotator_id is not None else existing.annotator_id,
        notes=data.notes if data.notes is not None else existing.notes,
    )

    label = store.upsert_document_quality_label(updated)
    return _doc_label_to_response(label)


@router.delete("/documents/{label_id}", status_code=204)
def delete_document_quality_label(
    label_id: str,
    store: GoldStore = Depends(get_store),
):
    """Delete a document quality label."""
    deleted = store.delete_document_quality_label(label_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document quality label not found")


# --- Span Quality Label endpoints ---


@router.post("/spans", response_model=SpanQualityLabelResponse, status_code=201)
def create_span_quality_label(
    data: SpanQualityLabelCreate,
    store: GoldStore = Depends(get_store),
) -> SpanQualityLabelResponse:
    """Create a span quality label."""
    label = store.create_span_quality_label(
        span_id=data.span_id,
        extraction_quality=data.extraction_quality.value if data.extraction_quality else None,
        grounding_quality=data.grounding_quality.value if data.grounding_quality else None,
        evidence_usability=data.evidence_usability.value if data.evidence_usability else None,
        annotator_id=data.annotator_id,
        notes=data.notes,
    )
    return _span_label_to_response(label)


@router.get("/spans", response_model=SpanQualityLabelListResponse)
def list_span_quality_labels(
    span_id: str | None = Query(None),
    extraction_quality: str | None = Query(None),
    grounding_quality: str | None = Query(None),
    evidence_usability: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    store: GoldStore = Depends(get_store),
) -> SpanQualityLabelListResponse:
    """List span quality labels with optional filters."""
    labels, total = store.list_span_quality_labels(
        span_id=span_id,
        extraction_quality=extraction_quality,
        grounding_quality=grounding_quality,
        evidence_usability=evidence_usability,
        limit=limit,
        offset=offset,
    )
    return SpanQualityLabelListResponse(
        labels=[_span_label_to_response(label) for label in labels],
        total=total,
    )


@router.get("/spans/{label_id}", response_model=SpanQualityLabelResponse)
def get_span_quality_label(
    label_id: str,
    store: GoldStore = Depends(get_store),
) -> SpanQualityLabelResponse:
    """Get a span quality label by ID."""
    label = store.get_span_quality_label(label_id)
    if not label:
        raise HTTPException(status_code=404, detail="Span quality label not found")
    return _span_label_to_response(label)


@router.put("/spans/{label_id}", response_model=SpanQualityLabelResponse)
def update_span_quality_label(
    label_id: str,
    data: SpanQualityLabelUpdate,
    store: GoldStore = Depends(get_store),
) -> SpanQualityLabelResponse:
    """Update a span quality label."""
    existing = store.get_span_quality_label(label_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Span quality label not found")

    updated = SpanQualityLabel(
        id=existing.id,
        span_id=existing.span_id,
        extraction_quality=(
            data.extraction_quality.value if data.extraction_quality else existing.extraction_quality
        ),
        grounding_quality=data.grounding_quality.value if data.grounding_quality else existing.grounding_quality,
        evidence_usability=data.evidence_usability.value if data.evidence_usability else existing.evidence_usability,
        annotator_id=data.annotator_id if data.annotator_id is not None else existing.annotator_id,
        notes=data.notes if data.notes is not None else existing.notes,
    )

    label = store.upsert_span_quality_label(updated)
    return _span_label_to_response(label)


@router.delete("/spans/{label_id}", status_code=204)
def delete_span_quality_label(
    label_id: str,
    store: GoldStore = Depends(get_store),
):
    """Delete a span quality label."""
    deleted = store.delete_span_quality_label(label_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Span quality label not found")
