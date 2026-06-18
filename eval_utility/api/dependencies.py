"""Dependency injection for the annotation API."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from ..config import Settings, get_settings
from ..store import GoldStore


@lru_cache
def get_cached_settings() -> Settings:
    """Get cached settings instance."""
    return get_settings()


def get_store() -> GoldStore:
    """Get a GoldStore instance."""
    settings = get_cached_settings()
    return GoldStore(settings=settings)


def get_fixtures_dir() -> Path:
    """Get the fixtures directory path."""
    return get_cached_settings().fixtures_dir
