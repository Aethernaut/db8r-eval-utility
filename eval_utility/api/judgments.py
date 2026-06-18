"""Retrieval judgment (T1) endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response

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


@router.get("", response_model=RetrievalJudgmentListResponse)
def list_judgments(
    claim_id: str | None = Query(None),
    document_id: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    store: GoldStore = Depends(get_store),
) -> RetrievalJudgmentListResponse:
    """List retrieval judgments (filter by claim_id, document_id)."""
    with store._connect() as conn:
        query = "SELECT * FROM retrieval_judgment WHERE 1=1"
        count_query = "SELECT COUNT(*) FROM retrieval_judgment WHERE 1=1"
        params: list = []
        count_params: list = []

        if claim_id is not None:
            query += " AND claim_id = ?"
            count_query += " AND claim_id = ?"
            params.append(claim_id)
            count_params.append(claim_id)

        if document_id is not None:
            query += " AND document_id = ?"
            count_query += " AND document_id = ?"
            params.append(document_id)
            count_params.append(document_id)

        query += " ORDER BY claim_id, retrieval_rank LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = conn.execute(query, params).fetchall()
        count_row = conn.execute(count_query, count_params).fetchone()

    judgments = [_judgment_to_response(RetrievalJudgment(**dict(row))) for row in rows]

    return RetrievalJudgmentListResponse(judgments=judgments, total=count_row[0])


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
    with store._connect() as conn:
        row = conn.execute(
            "SELECT * FROM retrieval_judgment WHERE claim_id = ? AND document_id = ?",
            (claim_id, document_id),
        ).fetchone()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Judgment for claim {claim_id} and document {document_id} not found",
        )

    judgment = RetrievalJudgment(**dict(row))

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
    with store._connect() as conn:
        row = conn.execute(
            "SELECT * FROM retrieval_judgment WHERE claim_id = ? AND document_id = ?",
            (claim_id, document_id),
        ).fetchone()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Judgment for claim {claim_id} and document {document_id} not found",
        )

    with store._connect() as conn:
        conn.execute(
            "DELETE FROM retrieval_judgment WHERE claim_id = ? AND document_id = ?",
            (claim_id, document_id),
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
        with store._connect() as conn:
            row = conn.execute(
                "SELECT * FROM retrieval_judgment WHERE claim_id = ? AND document_id = ?",
                (judgment_data.claim_id, judgment_data.document_id),
            ).fetchone()

        is_update = row is not None

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
