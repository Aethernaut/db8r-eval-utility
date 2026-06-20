"""Claim-span label (T3) endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select

from ..database import session_scope
from ..models import ClaimSpanLabelModel
from ..store import ClaimSpanLabel, GoldStore
from .dependencies import get_store
from .schemas import (
    ClaimSpanLabelCreate,
    ClaimSpanLabelListResponse,
    ClaimSpanLabelResponse,
    ClaimSpanLabelUpdate,
    LabelBatchRequest,
    LabelBatchResponse,
)

router = APIRouter()


def _label_to_response(label: ClaimSpanLabel) -> ClaimSpanLabelResponse:
    """Convert ClaimSpanLabel to response model."""
    return ClaimSpanLabelResponse(
        claim_id=label.claim_id,
        span_id=label.span_id,
        relevant_to_claim=label.relevant_to_claim,
        stance=label.stance,
        strength_ordinal=label.strength_ordinal,
        annotator_id=label.annotator_id,
        notes=label.notes,
        created_at=label.created_at,
        updated_at=label.updated_at,
    )


def _model_to_label(m: ClaimSpanLabelModel) -> ClaimSpanLabel:
    """Convert SQLAlchemy model to dataclass."""
    return ClaimSpanLabel(
        claim_id=m.claim_id,
        span_id=m.span_id,
        relevant_to_claim=m.relevant_to_claim,
        stance=m.stance,
        strength_ordinal=m.strength_ordinal,
        annotator_id=m.annotator_id,
        notes=m.notes,
        created_at=m.created_at.isoformat() if m.created_at else "",
        updated_at=m.updated_at.isoformat() if m.updated_at else "",
    )


@router.get("", response_model=ClaimSpanLabelListResponse)
def list_labels(
    claim_id: str | None = Query(None),
    span_id: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    store: GoldStore = Depends(get_store),
) -> ClaimSpanLabelListResponse:
    """List claim-span labels (filter by claim_id, span_id)."""
    with session_scope() as session:
        stmt = select(ClaimSpanLabelModel)
        count_stmt = select(func.count()).select_from(ClaimSpanLabelModel)

        if claim_id is not None:
            stmt = stmt.where(ClaimSpanLabelModel.claim_id == claim_id)
            count_stmt = count_stmt.where(ClaimSpanLabelModel.claim_id == claim_id)

        if span_id is not None:
            stmt = stmt.where(ClaimSpanLabelModel.span_id == span_id)
            count_stmt = count_stmt.where(ClaimSpanLabelModel.span_id == span_id)

        stmt = stmt.order_by(ClaimSpanLabelModel.claim_id, ClaimSpanLabelModel.span_id)
        stmt = stmt.offset(offset).limit(limit)

        models = session.execute(stmt).scalars().all()
        total = session.execute(count_stmt).scalar() or 0

    labels = [_label_to_response(_model_to_label(m)) for m in models]
    return ClaimSpanLabelListResponse(labels=labels, total=total)


@router.post("", response_model=ClaimSpanLabelResponse, status_code=201)
def create_label(
    data: ClaimSpanLabelCreate,
    store: GoldStore = Depends(get_store),
) -> ClaimSpanLabelResponse:
    """Create a claim-span label."""
    # Verify claim exists
    claim = store.get_claim(data.claim_id)
    if claim is None:
        raise HTTPException(status_code=404, detail=f"Claim {data.claim_id} not found")

    # Verify span exists
    span = store.get_gold_span(data.span_id)
    if span is None:
        raise HTTPException(status_code=404, detail=f"Span {data.span_id} not found")

    label = ClaimSpanLabel(
        claim_id=data.claim_id,
        span_id=data.span_id,
        relevant_to_claim=data.relevant_to_claim,
        stance=data.stance.value if data.stance else None,
        strength_ordinal=data.strength_ordinal.value if data.strength_ordinal else None,
        annotator_id=data.annotator_id,
        notes=data.notes,
    )
    label = store.upsert_claim_span_label(label)
    return _label_to_response(label)


@router.put("/{claim_id}/{span_id}", response_model=ClaimSpanLabelResponse)
def update_label(
    claim_id: str,
    span_id: str,
    data: ClaimSpanLabelUpdate,
    store: GoldStore = Depends(get_store),
) -> ClaimSpanLabelResponse:
    """Update a claim-span label."""
    # Get existing label (using 'system' as default annotator for backwards compat)
    label = store.get_label(claim_id, span_id)

    if label is None:
        raise HTTPException(
            status_code=404,
            detail=f"Label for claim {claim_id} and span {span_id} not found",
        )

    # Apply updates
    if data.relevant_to_claim is not None:
        label.relevant_to_claim = data.relevant_to_claim
    if data.stance is not None:
        label.stance = data.stance.value
    if data.strength_ordinal is not None:
        label.strength_ordinal = data.strength_ordinal.value
    if data.annotator_id is not None:
        label.annotator_id = data.annotator_id
    if data.notes is not None:
        label.notes = data.notes

    label = store.upsert_claim_span_label(label)
    return _label_to_response(label)


@router.delete("/{claim_id}/{span_id}", status_code=204)
def delete_label(
    claim_id: str,
    span_id: str,
    store: GoldStore = Depends(get_store),
) -> Response:
    """Delete a claim-span label."""
    label = store.get_label(claim_id, span_id)

    if label is None:
        raise HTTPException(
            status_code=404,
            detail=f"Label for claim {claim_id} and span {span_id} not found",
        )

    deleted = store.delete_claim_span_label(claim_id, span_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Label for claim {claim_id} and span {span_id} not found",
        )

    return Response(status_code=204)


@router.post("/batch", response_model=LabelBatchResponse)
def batch_upsert_labels(
    data: LabelBatchRequest,
    store: GoldStore = Depends(get_store),
) -> LabelBatchResponse:
    """Batch upsert claim-span labels."""
    created_count = 0
    updated_count = 0
    result_labels = []

    for label_data in data.labels:
        # Check if label exists
        existing = store.get_label(label_data.claim_id, label_data.span_id)
        is_update = existing is not None

        label = ClaimSpanLabel(
            claim_id=label_data.claim_id,
            span_id=label_data.span_id,
            relevant_to_claim=label_data.relevant_to_claim,
            stance=label_data.stance.value if label_data.stance else None,
            strength_ordinal=label_data.strength_ordinal.value if label_data.strength_ordinal else None,
            annotator_id=label_data.annotator_id,
            notes=label_data.notes,
        )
        label = store.upsert_claim_span_label(label)
        result_labels.append(label)

        if is_update:
            updated_count += 1
        else:
            created_count += 1

    return LabelBatchResponse(
        created_count=created_count,
        updated_count=updated_count,
        labels=[_label_to_response(label) for label in result_labels],
    )
