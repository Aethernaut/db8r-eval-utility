"""Configuration for the eval utility.

The tool is a ClaimCheck *client*: it calls ClaimCheck's HTTP API to capture fixtures,
then annotates/scores fully offline. It connects to NO production database.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="EVAL_", env_file=".env", extra="ignore")

    # ClaimCheck client (capture only)
    claimcheck_base_url: str = "http://127.0.0.1:8001"
    claimcheck_timeout_seconds: float = 120.0

    # Storage (own store — never a production DB)
    fixtures_dir: Path = ROOT_DIR / "fixtures"
    gold_db_path: Path = ROOT_DIR / "gold" / "gold.db"

    # Scoring
    span_match_iou_threshold: float = 0.5  # τ for gold↔extracted span matching
    retrieval_top_k: int = 10

    # Dataset
    schema_version: str = "gold_v1"


def get_settings() -> Settings:
    return Settings()
