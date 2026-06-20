"""EU-4/EU-8 — Annotation API server (FastAPI).

FastAPI backend for annotation UI. External frontend will consume this API.
Supports three annotation tasks:
  - T1: Retrieval judgment (claim × document relevance)
  - T2: Span annotation (gold span creation/editing)
  - T3: Stance/strength labeling (claim × span)

EU-8 adds:
  - Cookie-session auth (httpOnly, Secure, SameSite=Strict)
  - Invite-only accounts with admin/annotator roles
  - CSRF protection on state-changing routes
"""

from __future__ import annotations

from contextlib import asynccontextmanager

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
from .api.auth_routes import bootstrap_admin
from .api.auth_routes import router as auth_router
from .api.schemas import HealthResponse
from .api.users import router as users_router
from .config import get_settings
from .database import check_db_connectivity, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    # Startup
    settings = get_settings()

    # Initialize database
    init_db()

    # Bootstrap admin if env vars are set
    admin = bootstrap_admin(settings)
    if admin:
        print(f"Bootstrapped admin user: {admin.email}")

    yield

    # Shutdown (cleanup if needed)


app = FastAPI(
    title="DB8R Eval Utility",
    description="Annotation API for DB8R evidence pipeline evaluation",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS (restricted via EVAL_CORS_ORIGIN)
settings = get_settings()
origins = [settings.cors_origin] if settings.cors_origin != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth routes (no prefix)
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(users_router, prefix="/api/v1/users", tags=["users"])

# Data routes
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
    """Service health check with DB connectivity."""
    db_ok = check_db_connectivity()
    return HealthResponse(
        status="healthy" if db_ok else "unhealthy",
        version="0.1.0",
        database_connected=db_ok,
    )
