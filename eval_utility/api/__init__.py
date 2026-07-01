"""API module for the annotation server."""

from .claims import router as claims_router
from .dataset import router as dataset_router
from .documents import router as documents_router
from .fixtures import router as fixtures_router
from .foraging import router as foraging_router
from .judgments import router as judgments_router
from .labels import router as labels_router
from .quality_labels import router as quality_labels_router
from .spans import router as spans_router

__all__ = [
    "claims_router",
    "dataset_router",
    "documents_router",
    "fixtures_router",
    "foraging_router",
    "judgments_router",
    "labels_router",
    "quality_labels_router",
    "spans_router",
]
