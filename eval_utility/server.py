"""EU-4 — Annotation API server (FastAPI).

FastAPI backend for annotation UI. External frontend will consume this API.
Supports three annotation tasks:
  - T1: Retrieval judgment (claim × document relevance)
  - T2: Span annotation (gold span creation/editing)
  - T3: Stance/strength labeling (claim × span)
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import (
    claims_router,
    dataset_router,
    documents_router,
    fixtures_router,
    foraging_router,
    judgments_router,
    labels_router,
    spans_router,
)
from .api.schemas import HealthResponse

app = FastAPI(
    title="DB8R Eval Utility",
    description="Annotation API for DB8R evidence pipeline evaluation",
    version="0.1.0",
)

# Configure CORS for external frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(fixtures_router, prefix="/api/v1/fixtures", tags=["fixtures"])
app.include_router(claims_router, prefix="/api/v1/claims", tags=["claims"])
app.include_router(documents_router, prefix="/api/v1/documents", tags=["documents"])
app.include_router(spans_router, prefix="/api/v1/spans", tags=["spans"])
app.include_router(labels_router, prefix="/api/v1/labels", tags=["labels"])
app.include_router(judgments_router, prefix="/api/v1/judgments", tags=["judgments"])
app.include_router(foraging_router, prefix="/api/v1/foraging", tags=["foraging"])
app.include_router(dataset_router, prefix="/api/v1/dataset", tags=["dataset"])


@app.get("/health", response_model=HealthResponse, tags=["health"])
def health_check() -> HealthResponse:
    """Service health check."""
    return HealthResponse(status="healthy", version="0.1.0")
