"""Claim CRUD endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from ..store import Claim, ClaimDocumentLink, GoldStore
from .dependencies import get_store
from .schemas import (
    ClaimCreate,
    ClaimDocumentLinkCreate,
    ClaimDocumentLinkResponse,
    ClaimListResponse,
    ClaimResponse,
    ClaimUpdate,
)

router = APIRouter()


def _claim_to_response(claim: Claim) -> ClaimResponse:
    """Convert Claim to response model."""
    return ClaimResponse(
        claim_id=claim.claim_id,
        text=claim.text,
        family=claim.family,
        proof_standard=claim.proof_standard,
        split=claim.split,
        notes=claim.notes,
        created_at=claim.created_at,
        updated_at=claim.updated_at,
    )


def _link_to_response(link: ClaimDocumentLink) -> ClaimDocumentLinkResponse:
    """Convert ClaimDocumentLink to response model."""
    return ClaimDocumentLinkResponse(
        claim_id=link.claim_id,
        document_id=link.document_id,
        origin=link.origin,
        fixture_id=link.fixture_id,
        notes=link.notes,
        created_at=link.created_at,
    )


@router.get("", response_model=ClaimListResponse)
def list_claims(
    split: str | None = Query(None),
    family: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    store: GoldStore = Depends(get_store),
) -> ClaimListResponse:
    """List claims (filter by split, family)."""
    claims = store.list_claims(split=split, family=family)
    total = len(claims)
    paginated = claims[offset : offset + limit]
    return ClaimListResponse(
        claims=[_claim_to_response(c) for c in paginated],
        total=total,
    )


@router.post("", response_model=ClaimResponse, status_code=201)
def create_claim(
    data: ClaimCreate,
    store: GoldStore = Depends(get_store),
) -> ClaimResponse:
    """Create a claim."""
    claim = Claim(
        claim_id=f"claim-{uuid.uuid4().hex[:12]}",
        text=data.text,
        family=data.family.value if data.family else None,
        proof_standard=data.proof_standard.value if data.proof_standard else None,
        split=data.split.value if data.split else "train",
        notes=data.notes,
    )
    claim = store.upsert_claim(claim)
    return _claim_to_response(claim)


@router.get("/{claim_id}", response_model=ClaimResponse)
def get_claim(
    claim_id: str,
    store: GoldStore = Depends(get_store),
) -> ClaimResponse:
    """Get a claim."""
    claim = store.get_claim(claim_id)
    if claim is None:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")
    return _claim_to_response(claim)


@router.put("/{claim_id}", response_model=ClaimResponse)
def update_claim(
    claim_id: str,
    data: ClaimUpdate,
    store: GoldStore = Depends(get_store),
) -> ClaimResponse:
    """Update a claim."""
    claim = store.get_claim(claim_id)
    if claim is None:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")

    # Apply updates
    if data.text is not None:
        claim.text = data.text
    if data.family is not None:
        claim.family = data.family.value
    if data.proof_standard is not None:
        claim.proof_standard = data.proof_standard.value
    if data.split is not None:
        claim.split = data.split.value
    if data.notes is not None:
        claim.notes = data.notes

    claim = store.upsert_claim(claim)
    return _claim_to_response(claim)


@router.delete("/{claim_id}", status_code=204)
def delete_claim(
    claim_id: str,
    store: GoldStore = Depends(get_store),
) -> Response:
    """Delete a claim."""
    claim = store.get_claim(claim_id)
    if claim is None:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")

    deleted = store.delete_claim(claim_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")

    return Response(status_code=204)


@router.get("/{claim_id}/documents", response_model=list[ClaimDocumentLinkResponse])
def list_claim_documents(
    claim_id: str,
    store: GoldStore = Depends(get_store),
) -> list[ClaimDocumentLinkResponse]:
    """List documents linked to a claim."""
    claim = store.get_claim(claim_id)
    if claim is None:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")

    links = store.get_documents_for_claim(claim_id)
    return [_link_to_response(link) for link in links]


@router.post("/{claim_id}/documents", response_model=ClaimDocumentLinkResponse, status_code=201)
def link_document_to_claim(
    claim_id: str,
    data: ClaimDocumentLinkCreate,
    store: GoldStore = Depends(get_store),
) -> ClaimDocumentLinkResponse:
    """Link a document to a claim."""
    claim = store.get_claim(claim_id)
    if claim is None:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")

    link = ClaimDocumentLink(
        claim_id=claim_id,
        document_id=data.document_id,
        origin=data.origin.value if data.origin else "manual",
        fixture_id=data.fixture_id,
        notes=data.notes,
    )
    link = store.upsert_claim_document_link(link)
    return _link_to_response(link)
