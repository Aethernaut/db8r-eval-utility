"""Retrieval judgment (T1) endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select

from ..database import session_scope
from ..models import RetrievalJudgmentModel
from ..store import GoldStore, RetrievalJudgment
from .dependencies import get_store
from .schemas import (
    JudgmentBatchRequest,
    JudgmentBatchResponse,
    RetrievalJudgmentCreate,
    RetrievalJudgmentListResponse,
    RetrievalJudgmentResponse,
    RetrievalJudgmentUpdate,
)

router = APIRouter()


def _judgment_to_response(judgment: RetrievalJudgment) -> RetrievalJudgmentResponse:
    """Convert RetrievalJudgment to response model."""
    return RetrievalJudgmentResponse(
        claim_id=judgment.claim_id,
        document_id=judgment.document_id,
        forage_query_id=judgment.forage_query_id,
        relevant=judgment.relevant,
        retrieval_rank=judgment.retrieval_rank,
        annotator_id=judgment.annotator_id,
        notes=judgment.notes,
        created_at=judgment.created_at,
        updated_at=judgment.updated_at,
    )


def _model_to_judgment(m: RetrievalJudgmentModel) -> RetrievalJudgment:
    """Convert SQLAlchemy model to dataclass."""
    return RetrievalJudgment(
        claim_id=m.claim_id,
        document_id=m.document_id,
        forage_query_id=m.forage_query_id,
        relevant=m.relevant,
        retrieval_rank=m.retrieval_rank,
        annotator_id=m.annotator_id,
        notes=m.notes,
        created_at=m.created_at.isoformat() if m.created_at else "",
        updated_at=m.updated_at.isoformat() if m.updated_at else "",
    )


@router.get("", response_model=RetrievalJudgmentListResponse)
def list_judgments(
    claim_id: str | None = Query(None),
    document_id: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    store: GoldStore = Depends(get_store),
) -> RetrievalJudgmentListResponse:
    """List retrieval judgments (filter by claim_id, document_id)."""
    with session_scope() as session:
        stmt = select(RetrievalJudgmentModel)
        count_stmt = select(func.count()).select_from(RetrievalJudgmentModel)

        if claim_id is not None:
            stmt = stmt.where(RetrievalJudgmentModel.claim_id == claim_id)
            count_stmt = count_stmt.where(RetrievalJudgmentModel.claim_id == claim_id)

        if document_id is not None:
            stmt = stmt.where(RetrievalJudgmentModel.document_id == document_id)
            count_stmt = count_stmt.where(RetrievalJudgmentModel.document_id == document_id)

        stmt = stmt.order_by(RetrievalJudgmentModel.claim_id, RetrievalJudgmentModel.retrieval_rank)
        stmt = stmt.offset(offset).limit(limit)

        models = session.execute(stmt).scalars().all()
        total = session.execute(count_stmt).scalar() or 0

    judgments = [_judgment_to_response(_model_to_judgment(m)) for m in models]
    return RetrievalJudgmentListResponse(judgments=judgments, total=total)


@router.post("", response_model=RetrievalJudgmentResponse, status_code=201)
def create_judgment(
    data: RetrievalJudgmentCreate,
    store: GoldStore = Depends(get_store),
) -> RetrievalJudgmentResponse:
    """Create a retrieval judgment."""
    # Verify claim exists
    claim = store.get_claim(data.claim_id)
    if claim is None:
        raise HTTPException(status_code=404, detail=f"Claim {data.claim_id} not found")

    judgment = RetrievalJudgment(
        claim_id=data.claim_id,
        document_id=data.document_id,
        forage_query_id=data.forage_query_id,
        relevant=data.relevant,
        retrieval_rank=data.retrieval_rank,
        annotator_id=data.annotator_id,
        notes=data.notes,
    )
    judgment = store.upsert_retrieval_judgment(judgment)
    return _judgment_to_response(judgment)


@router.put("/{claim_id}/{document_id}", response_model=RetrievalJudgmentResponse)
def update_judgment(
    claim_id: str,
    document_id: str,
    data: RetrievalJudgmentUpdate,
    store: GoldStore = Depends(get_store),
) -> RetrievalJudgmentResponse:
    """Update a retrieval judgment."""
    # Get existing judgment (using 'system' as default annotator for backwards compat)
    judgment = store.get_judgment(claim_id, document_id)

    if judgment is None:
        raise HTTPException(
            status_code=404,
            detail=f"Judgment for claim {claim_id} and document {document_id} not found",
        )

    # Apply updates
    if data.forage_query_id is not None:
        judgment.forage_query_id = data.forage_query_id
    if data.relevant is not None:
        judgment.relevant = data.relevant
    if data.retrieval_rank is not None:
        judgment.retrieval_rank = data.retrieval_rank
    if data.annotator_id is not None:
        judgment.annotator_id = data.annotator_id
    if data.notes is not None:
        judgment.notes = data.notes

    judgment = store.upsert_retrieval_judgment(judgment)
    return _judgment_to_response(judgment)


@router.delete("/{claim_id}/{document_id}", status_code=204)
def delete_judgment(
    claim_id: str,
    document_id: str,
    store: GoldStore = Depends(get_store),
) -> Response:
    """Delete a retrieval judgment."""
    judgment = store.get_judgment(claim_id, document_id)

    if judgment is None:
        raise HTTPException(
            status_code=404,
            detail=f"Judgment for claim {claim_id} and document {document_id} not found",
        )

    deleted = store.delete_retrieval_judgment(claim_id, document_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Judgment for claim {claim_id} and document {document_id} not found",
        )

    return Response(status_code=204)


@router.post("/batch", response_model=JudgmentBatchResponse)
def batch_upsert_judgments(
    data: JudgmentBatchRequest,
    store: GoldStore = Depends(get_store),
) -> JudgmentBatchResponse:
    """Batch upsert retrieval judgments."""
    created_count = 0
    updated_count = 0
    result_judgments = []

    for judgment_data in data.judgments:
        # Check if judgment exists
        existing = store.get_judgment(judgment_data.claim_id, judgment_data.document_id)
        is_update = existing is not None

        judgment = RetrievalJudgment(
            claim_id=judgment_data.claim_id,
            document_id=judgment_data.document_id,
            forage_query_id=judgment_data.forage_query_id,
            relevant=judgment_data.relevant,
            retrieval_rank=judgment_data.retrieval_rank,
            annotator_id=judgment_data.annotator_id,
            notes=judgment_data.notes,
        )
        judgment = store.upsert_retrieval_judgment(judgment)
        result_judgments.append(judgment)

        if is_update:
            updated_count += 1
        else:
            created_count += 1

    return JudgmentBatchResponse(
        created_count=created_count,
        updated_count=updated_count,
        judgments=[_judgment_to_response(j) for j in result_judgments],
    )
