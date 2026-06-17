"""EU-2 — Capture client. Drives ClaimCheck to produce immutable, hashed fixtures.

Three modes (README §3):
  A) unilateral search   -> POST /api/v1/search   {query, providers?}
  B) direct document     -> POST /api/v1/extract  {url | raw_text, query?}
  C) debate import       -> load a previously captured /search response

A captured response is frozen as fixtures/<source_text_hash-derived>.json. Record the
per-document `extraction_status` (CC-3a) so partial fixtures are flagged.

TODO(EU-2): implement httpx calls, freezing, and hashing. Stubs below define the surface.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import Settings, get_settings


@dataclass(frozen=True)
class CaptureResult:
    fixture_id: str
    fixture_path: str
    capture_mode: str  # "search_A" | "extract_B" | "debate_C"


class CaptureClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def search(self, query: str, providers: list[str] | None = None) -> CaptureResult:  # Mode A
        raise NotImplementedError("EU-2: POST /api/v1/search, freeze + hash response into a fixture")

    def extract(self, *, url: str | None = None, raw_text: str | None = None, query: str | None = None) -> CaptureResult:  # Mode B
        raise NotImplementedError("EU-2: POST /api/v1/extract, freeze + hash response into a fixture")

    def import_response(self, response_json_path: str) -> CaptureResult:  # Mode C
        raise NotImplementedError("EU-2: load + validate + freeze an existing /search response")
