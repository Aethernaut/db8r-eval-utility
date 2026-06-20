"""Configuration for the eval utility.

The tool is a ClaimCheck *client*: it calls ClaimCheck's HTTP API to capture fixtures,
then annotates/scores fully offline. It connects to NO production database.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="EVAL_", env_file=".env", extra="ignore")

    # ClaimCheck client (capture only)
    claimcheck_base_url: str = "http://127.0.0.1:8001"
    claimcheck_timeout_seconds: float = 120.0

    # db8r-mcts client — foraging-strategy capture only (MC-5 /api/v1/foraging-strategy)
    db8r_mcts_base_url: str = "http://127.0.0.1:8000"
    db8r_mcts_timeout_seconds: float = 60.0

    # Storage (own store — never a production DB)
    # DATABASE_URL supports SQLite (tests/local) and Postgres (deploy)
    database_url: str = f"sqlite:///{ROOT_DIR / 'gold' / 'gold.db'}"
    fixtures_dir: Path = ROOT_DIR / "fixtures"

    # Legacy: gold_db_path derived from database_url for backwards compat
    @property
    def gold_db_path(self) -> Path:
        """Extract SQLite path from database_url for backwards compat."""
        if self.database_url.startswith("sqlite:///"):
            return Path(self.database_url.replace("sqlite:///", ""))
        return ROOT_DIR / "gold" / "gold.db"

    # Capture options
    # Request per-request full-document extraction (CC-10b) so captures aren't truncated
    # at the server's default char cap. Opt-in per call; does not touch the shared server flag.
    capture_full_document_extraction: bool = True

    # Scoring
    span_match_iou_threshold: float = 0.5  # τ for gold↔extracted span matching
    retrieval_top_k: int = 10

    # Dataset
    schema_version: str = "gold_v1"

    # Auth (EU-8)
    cors_origin: str = "*"  # Restrict in prod via EVAL_CORS_ORIGIN
    admin_email: str | None = None  # Bootstrap admin: EVAL_ADMIN_EMAIL
    admin_initial_password: str | None = None  # Bootstrap admin: EVAL_ADMIN_INITIAL_PASSWORD
    session_ttl_hours: int = 24
    invite_token_ttl_hours: int = 72
    session_cookie_name: str = "eval_session"
    session_cookie_secure: bool = False  # Set True in prod (HTTPS only)

    # Rate limiting (EU-8)
    login_rate_limit_attempts: int = 5
    login_rate_limit_window_seconds: int = 300  # 5 minutes

    # Capture jobs (EU-10)
    capture_job_concurrency_limit: int = 3

    @field_validator("cors_origin")
    @classmethod
    def validate_cors_origin(cls, v: str) -> str:
        # Warn about wildcard in non-dev contexts (actual enforcement in prod config)
        return v


def get_settings() -> Settings:
    return Settings()
