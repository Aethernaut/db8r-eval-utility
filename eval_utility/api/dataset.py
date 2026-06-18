"""Dataset metadata endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..store import GoldStore
from .dependencies import get_store
from .schemas import DatasetResponse, DatasetUpdate

router = APIRouter()


@router.get("", response_model=DatasetResponse)
def get_dataset(
    store: GoldStore = Depends(get_store),
) -> DatasetResponse:
    """Get dataset metadata and record counts."""
    dataset = store.get_dataset()
    counts = store.count_records()

    return DatasetResponse(
        dataset_version=dataset.dataset_version,
        schema_version=dataset.schema_version,
        annotation_guidelines_version=dataset.annotation_guidelines_version,
        created_at=dataset.created_at,
        updated_at=dataset.updated_at,
        record_counts=counts,
    )


@router.put("", response_model=DatasetResponse)
def update_dataset(
    update: DatasetUpdate,
    store: GoldStore = Depends(get_store),
) -> DatasetResponse:
    """Update dataset version info."""
    store.update_dataset(
        dataset_version=update.dataset_version,
        annotation_guidelines_version=update.annotation_guidelines_version,
    )

    dataset = store.get_dataset()
    counts = store.count_records()

    return DatasetResponse(
        dataset_version=dataset.dataset_version,
        schema_version=dataset.schema_version,
        annotation_guidelines_version=dataset.annotation_guidelines_version,
        created_at=dataset.created_at,
        updated_at=dataset.updated_at,
        record_counts=counts,
    )
