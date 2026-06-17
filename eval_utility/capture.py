"""EU-2 — Capture client. Drives ClaimCheck to produce immutable, hashed fixtures.

Three modes (README §3):
  A) unilateral search   -> POST /api/v1/search   {query, providers?, include_evidence_documents=true}
  B) direct document     -> POST /api/v1/extract  {url | raw_text, query?}
  C) debate import       -> load a previously captured /search response

EU-2f foraging capture:
  POST /api/v1/foraging-strategy to db8r-mcts (MC-5) -> replay each query via Mode A

A captured response is frozen as fixtures/<fixture_id>.json. Each document is
content-addressed by `source_text_hash` so labels survive foraging enrichment.
Record per-document `extraction_status` (CC-3a) so partial fixtures can be excluded.

Key invariants:
  - Read span offsets from the response `claims[]` array only (projections carry null offsets)
  - Documents are content-addressed by source_text_hash
  - Fixtures are immutable once written
  - Gold labels key only to claim/content-addressed-document/span

ClaimCheck requirements (verified live 2026-06-17, CC-10a/10b landed):
  - Mode A `/search` is ASYNC: POST returns a pending job; the **poll GET must pass
    `?include_evidence_documents=true&include_source_text=true`** or the response has
    `evidence_documents: null` (the earlier "legacy_claim_fragment" was a cache effect, not a mode).
  - CC-10a: evidence documents carry full `source_text` + per-claim offsets when
    `include_source_text=true`. We read `source_text` directly (no lossy passage reconstruction).
  - CC-10b: pass `full_document_extraction=true` per request to avoid the server's char-cap
    truncation — no need to flip the shared `FULL_DOCUMENT_EXTRACTION_ENABLED` server flag.
  - Mode B (/extract) is synchronous and honors the same flags in its POST body.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from .config import Settings, get_settings
from .fixtures import source_text_hash


@dataclass(frozen=True)
class ExtractionStatus:
    """CC-3a partial-extraction status. Capture this so scorer can exclude partial docs."""

    partial_extraction: bool
    chunks_processed: int | None = None
    chunks_total: int | None = None
    tokens_used: int | None = None
    token_budget: int | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CapturedSpan:
    """An extracted span from claims[] — the system output to be scored.

    Offsets are read from claims[] (not projections which return null offsets).
    """

    claim_id: str
    document_id: str
    text: str  # claim.statement — may be normalized/repaired; use verbatim_span for offset scoring
    char_offset: int  # statement_offset from claims[]
    char_length: int  # statement_length from claims[]
    extraction_fidelity: float | None = None
    match_method: str | None = None  # exact|normalized|fuzzy
    source_assertion_opinion: dict[str, Any] | None = None
    claimset_orientation: str | None = None
    relevance_score: float | None = None
    # CC-10a: exact source span (== source_text[offset:offset+length]); preferred for IoU/slicing.
    verbatim_span: str | None = None


@dataclass(frozen=True)
class CapturedDocument:
    """A document from evidence_documents[], content-addressed by source_text_hash."""

    document_id: str
    source_url: str
    source_title: str | None
    source_domain: str | None
    provider: str | None
    content_type: str | None  # Derived from URL or response
    fetched_at: str | None
    source_reliability: float | None
    retrieval_rank: int | None
    source_text: str
    source_text_hash: str
    source_text_char_len: int
    extraction_status: ExtractionStatus | None = None
    validation_warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RetrievalResult:
    """A ranked retrieval result from results[] (Mode A)."""

    document_id: str | None
    url: str
    title: str | None
    rank: int
    provider: str | None
    relevance_score: float | None
    status: str | None  # submitted|failed|etc
    error: str | None = None


@dataclass
class CapturedFixture:
    """The complete fixture: captured ClaimCheck output, immutable and hashed."""

    fixture_id: str
    capture_mode: str  # search_A | extract_B | debate_C
    query: str | None
    job_id: str | None
    claimcheck_version: str | None
    captured_at: str
    schema_version: str

    documents: list[CapturedDocument]
    spans: list[CapturedSpan]
    retrieval_results: list[RetrievalResult]

    # Job-level extraction status (CC-3a)
    extraction_status: ExtractionStatus | None = None

    # Foraging context (EU-2f) — set when captured via foraging
    forage_strategy_id: str | None = None
    forage_query_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON storage."""

        def convert(obj: Any) -> Any:
            if hasattr(obj, "__dataclass_fields__"):
                return {k: convert(v) for k, v in asdict(obj).items()}
            if isinstance(obj, list):
                return [convert(item) for item in obj]
            if isinstance(obj, dict):
                return {k: convert(v) for k, v in obj.items()}
            return obj

        return convert(self)


@dataclass(frozen=True)
class CaptureResult:
    """Result of a capture operation."""

    fixture_id: str
    fixture_path: str
    capture_mode: str  # search_A | extract_B | debate_C


@dataclass
class ForageQuery:
    """A single query from a foraging strategy (MC-5)."""

    forage_query_id: str
    pool: str  # PRO | CON
    query: str
    strategy: str
    priority: float
    rank: int
    providers: list[str]
    # Extra fields from MC-5 response
    intent_label: str | None = None
    rationale: str | None = None
    retrieval_role: str | None = None
    scheme: str | None = None
    critical_question_family: str | None = None
    target_schema_need_id: str | None = None
    # Linked fixture after replay
    fixture_id: str | None = None


@dataclass
class ForageStrategy:
    """A foraging strategy from db8r-mcts MC-5."""

    forage_strategy_id: str
    claim: str
    mode: str  # pregame | reactive
    perspective: str  # supports_claim | contradicts_claim
    generator_version: str
    generator: str | None
    claim_type: str | None
    providers: list[str]
    queries: list[ForageQuery]
    captured_at: str
    # Extra response fields
    fallback_reason: str | None = None
    claim_decomposition: dict[str, Any] | None = None
    polarity_reversal: dict[str, Any] | None = None
    schema_plan: dict[str, Any] | None = None


@dataclass
class ForagingResult:
    """Result of foraging capture (EU-2f)."""

    strategy: ForageStrategy
    capture_results: list[CaptureResult]  # One per query


class CaptureError(Exception):
    """Raised when capture fails."""

    pass


class CaptureClient:
    """Client for capturing ClaimCheck/db8r-mcts responses as immutable fixtures."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._ensure_fixtures_dir()

    def _ensure_fixtures_dir(self) -> None:
        self.settings.fixtures_dir.mkdir(parents=True, exist_ok=True)

    def _http_client(self, base_url: str, timeout: float) -> httpx.Client:
        return httpx.Client(base_url=base_url, timeout=timeout)

    def _generate_fixture_id(self) -> str:
        return f"fix-{uuid.uuid4().hex[:16]}"

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _infer_content_type(self, url: str) -> str | None:
        """Infer content type from URL."""
        url_lower = url.lower()
        if url_lower.endswith(".pdf"):
            return "pdf"
        if url_lower.endswith((".html", ".htm")):
            return "html"
        if "claimcheck://raw-text" in url_lower:
            return "raw_text"
        return None

    def _reconstruct_source_text(self, evidence_doc: dict[str, Any]) -> str:
        """Reconstruct source_text from passages, sorted by char_start."""
        passages = evidence_doc.get("passages", [])
        if not passages:
            return ""

        # Sort by char_start
        sorted_passages = sorted(passages, key=lambda p: p.get("char_start", 0))

        # Build source_text by placing each passage at its char_start position
        # Handle potential gaps by padding with spaces
        result_chars: list[str] = []
        current_pos = 0

        for passage in sorted_passages:
            char_start = passage.get("char_start", 0)
            text = passage.get("text", "")

            # Pad if there's a gap
            if char_start > current_pos:
                result_chars.append(" " * (char_start - current_pos))
            elif char_start < current_pos:
                # Overlapping passages - skip already covered portion
                overlap = current_pos - char_start
                text = text[overlap:] if overlap < len(text) else ""
                char_start = current_pos

            result_chars.append(text)
            current_pos = max(current_pos, char_start + len(text))

        return "".join(result_chars)

    def _parse_extraction_status(self, status_dict: dict[str, Any] | None) -> ExtractionStatus | None:
        """Parse extraction_status from response."""
        if not status_dict:
            return None
        return ExtractionStatus(
            partial_extraction=status_dict.get("partial_extraction", False),
            chunks_processed=status_dict.get("chunks_processed"),
            chunks_total=status_dict.get("chunks_total"),
            tokens_used=status_dict.get("tokens_used"),
            token_budget=status_dict.get("token_budget"),
            warnings=status_dict.get("warnings", []),
        )

    def _extract_documents(
        self, response: dict[str, Any], raw_text_input: str | None = None
    ) -> dict[str, CapturedDocument]:
        """Extract CapturedDocuments from response, keyed by document_id.

        For raw_text Mode B, we use the input text as source_text.
        Otherwise, reconstruct from passages.
        """
        documents: dict[str, CapturedDocument] = {}
        evidence_docs = response.get("evidence_documents") or []

        for evidence_doc in evidence_docs:
            doc_id = evidence_doc.get("document_id")
            if not doc_id:
                continue

            # Source text precedence:
            #   1. raw_text input (Mode B raw_text — caller supplied the exact text)
            #   2. full `source_text` from the response (CC-10a — exact stored SourceDocument.text)
            #   3. lossy passage reconstruction (last resort; NOT offset-faithful, pre-CC-10a only)
            full_source_text = evidence_doc.get("source_text")
            if raw_text_input and len(evidence_docs) == 1:
                text = raw_text_input
            elif isinstance(full_source_text, str) and full_source_text:
                text = full_source_text
            else:
                text = self._reconstruct_source_text(evidence_doc)

            text_hash = source_text_hash(text)

            # Get retrieval rank from results if available
            retrieval_rank = None
            for i, result in enumerate(response.get("results", [])):
                if result.get("document_id") == doc_id:
                    retrieval_rank = i + 1
                    break

            # Parse per-document extraction_status
            doc_extraction_status = self._parse_extraction_status(evidence_doc.get("extraction_status"))

            documents[doc_id] = CapturedDocument(
                document_id=doc_id,
                source_url=evidence_doc.get("source_url", ""),
                source_title=evidence_doc.get("title"),
                source_domain=evidence_doc.get("source_domain"),
                provider=evidence_doc.get("provider"),
                content_type=self._infer_content_type(evidence_doc.get("source_url", "")),
                fetched_at=None,  # Not in response; could use collected_at from first claim
                source_reliability=evidence_doc.get("source_reliability_prior"),
                retrieval_rank=retrieval_rank,
                source_text=text,
                source_text_hash=text_hash,
                source_text_char_len=len(text),
                extraction_status=doc_extraction_status,
                validation_warnings=evidence_doc.get("validation_warnings", []),
            )

        return documents

    def _extract_spans(self, response: dict[str, Any]) -> list[CapturedSpan]:
        """Extract CapturedSpans from claims[] — the canonical source for offsets.

        Per spec: "Read offsets from the claims[] array only (projections return null offsets)."
        """
        spans: list[CapturedSpan] = []
        claims = response.get("claims", [])

        # CC-10a: evidence-document `extracted_claims` carry the exact `verbatim_span`
        # aligned to the offsets (top-level claim.statement may be normalized/repaired).
        # Map by claim_id so the span carries the offset-faithful text for scoring.
        verbatim_by_id: dict[str, str] = {}
        for ed in response.get("evidence_documents") or []:
            for ec in ed.get("extracted_claims") or []:
                cid = ec.get("claim_id")
                vs = ec.get("verbatim_span")
                if cid and isinstance(vs, str) and vs:
                    verbatim_by_id[cid] = vs

        for claim in claims:
            # Only include claims with valid offsets
            offset = claim.get("statement_offset")
            length = claim.get("statement_length")

            if offset is None or length is None:
                continue

            spans.append(
                CapturedSpan(
                    claim_id=claim.get("claim_id", ""),
                    document_id=claim.get("source_document_id", ""),
                    text=claim.get("statement", ""),
                    char_offset=offset,
                    char_length=length,
                    extraction_fidelity=claim.get("extraction_fidelity"),
                    match_method=claim.get("match_method"),
                    source_assertion_opinion=claim.get("source_assertion_opinion"),
                    claimset_orientation=claim.get("claimset_orientation"),
                    relevance_score=claim.get("relevance_score"),
                    verbatim_span=verbatim_by_id.get(claim.get("claim_id", "")),
                )
            )

        return spans

    def _extract_retrieval_results(self, response: dict[str, Any]) -> list[RetrievalResult]:
        """Extract ranked retrieval results from results[]."""
        results: list[RetrievalResult] = []

        for i, result in enumerate(response.get("results", [])):
            results.append(
                RetrievalResult(
                    document_id=result.get("document_id"),
                    url=result.get("url", ""),
                    title=result.get("title"),
                    rank=i + 1,
                    provider=result.get("provider"),
                    relevance_score=result.get("relevance_score"),
                    status=result.get("status"),
                    error=result.get("error"),
                )
            )

        return results

    def _save_fixture(self, fixture: CapturedFixture) -> str:
        """Save fixture to JSON file. Returns the file path."""
        fixture_path = self.settings.fixtures_dir / f"{fixture.fixture_id}.json"
        with open(fixture_path, "w", encoding="utf-8") as f:
            json.dump(fixture.to_dict(), f, indent=2, ensure_ascii=False)
        return str(fixture_path)

    def _poll_search_job(
        self, client: httpx.Client, job_id: str, poll_interval: float = 2.0, max_polls: int = 120
    ) -> dict[str, Any]:
        """Poll a search job until completion or failure."""
        for _ in range(max_polls):
            # The job-detail endpoint defaults these to false; without them the polled
            # response has evidence_documents: null (this was the Mode A capture bug).
            resp = client.get(
                f"/api/v1/search/jobs/{job_id}",
                params={"include_evidence_documents": "true", "include_source_text": "true"},
            )
            resp.raise_for_status()
            data = resp.json()

            status = data.get("status")
            if status == "completed":
                return data
            if status in ("failed", "error"):
                raise CaptureError(f"Search job {job_id} failed: {data.get('error') or data.get('errors')}")

            time.sleep(poll_interval)

        raise CaptureError(f"Search job {job_id} timed out after {max_polls * poll_interval}s")

    def search(
        self,
        query: str,
        providers: list[str] | None = None,
        forage_strategy_id: str | None = None,
        forage_query_id: str | None = None,
    ) -> CaptureResult:
        """Mode A: Unilateral search via POST /api/v1/search.

        Polls until completion (with include_evidence_documents + include_source_text),
        then freezes the response as a fixture.

        Requests `full_document_extraction` per-call (CC-10b) so captures aren't truncated;
        the poll then retrieves full `source_text` + offsets (CC-10a). No dependency on the
        shared server's FULL_DOCUMENT_EXTRACTION_ENABLED flag.
        """
        with self._http_client(self.settings.claimcheck_base_url, self.settings.claimcheck_timeout_seconds) as client:
            payload: dict[str, Any] = {
                "query": query,
                "include_evidence_documents": True,
                "include_source_text": True,  # CC-10a
                "full_document_extraction": self.settings.capture_full_document_extraction,  # CC-10b
            }
            if providers:
                payload["providers"] = providers

            resp = client.post("/api/v1/search", json=payload)
            resp.raise_for_status()
            initial = resp.json()

            job_id = initial.get("job_id")
            if not job_id:
                raise CaptureError("No job_id in search response")

            # Poll until complete
            response = self._poll_search_job(client, job_id)

        return self._freeze_response(
            response,
            capture_mode="search_A",
            query=query,
            forage_strategy_id=forage_strategy_id,
            forage_query_id=forage_query_id,
        )

    def extract(
        self,
        *,
        url: str | None = None,
        raw_text: str | None = None,
        query: str | None = None,
    ) -> CaptureResult:
        """Mode B: Direct document extraction via POST /api/v1/extract.

        Provide either url or raw_text (not both). The extract endpoint is synchronous.
        """
        if (url is None) == (raw_text is None):
            raise ValueError("Provide exactly one of 'url' or 'raw_text'")

        with self._http_client(self.settings.claimcheck_base_url, self.settings.claimcheck_timeout_seconds) as client:
            payload: dict[str, Any] = {
                "include_evidence_documents": True,
                "include_source_text": True,  # CC-10a — full source_text on the (synchronous) response
                "full_document_extraction": self.settings.capture_full_document_extraction,  # CC-10b
            }
            if url:
                payload["url"] = url
            if raw_text:
                payload["raw_text"] = raw_text
            if query:
                payload["query"] = query

            resp = client.post("/api/v1/extract", json=payload)
            resp.raise_for_status()
            response = resp.json()

        return self._freeze_response(
            response,
            capture_mode="extract_B",
            query=query,
            raw_text_input=raw_text,
        )

    def import_response(self, response_json_path: str) -> CaptureResult:
        """Mode C: Import a previously captured /search response.

        Validates and freezes the response as a new fixture.
        """
        path = Path(response_json_path)
        if not path.exists():
            raise CaptureError(f"Response file not found: {response_json_path}")

        with open(path, "r", encoding="utf-8") as f:
            response = json.load(f)

        # Validate it looks like a SearchJobResponse
        if "job_id" not in response and "claims" not in response:
            raise CaptureError("Invalid response format: missing job_id and claims")

        return self._freeze_response(
            response,
            capture_mode="debate_C",
            query=response.get("query"),
        )

    def _freeze_response(
        self,
        response: dict[str, Any],
        capture_mode: str,
        query: str | None,
        raw_text_input: str | None = None,
        forage_strategy_id: str | None = None,
        forage_query_id: str | None = None,
    ) -> CaptureResult:
        """Freeze a ClaimCheck response as an immutable fixture."""
        fixture_id = self._generate_fixture_id()

        # Extract documents (content-addressed by source_text_hash)
        documents = self._extract_documents(response, raw_text_input)

        # Extract spans from claims[] (the canonical source for offsets)
        spans = self._extract_spans(response)

        # Extract retrieval results (Mode A)
        retrieval_results = self._extract_retrieval_results(response)

        # Job-level extraction status
        extraction_status = self._parse_extraction_status(response.get("extraction_status"))

        fixture = CapturedFixture(
            fixture_id=fixture_id,
            capture_mode=capture_mode,
            query=query,
            job_id=response.get("job_id"),
            claimcheck_version=None,  # Could extract from headers if available
            captured_at=self._now_iso(),
            schema_version=self.settings.schema_version,
            documents=list(documents.values()),
            spans=spans,
            retrieval_results=retrieval_results,
            extraction_status=extraction_status,
            forage_strategy_id=forage_strategy_id,
            forage_query_id=forage_query_id,
        )

        fixture_path = self._save_fixture(fixture)

        return CaptureResult(
            fixture_id=fixture_id,
            fixture_path=fixture_path,
            capture_mode=capture_mode,
        )

    def capture_foraging(
        self,
        claim: str,
        perspective: str = "supports_claim",
        mode: str = "pregame",
        replay_queries: bool = True,
    ) -> ForagingResult:
        """EU-2f: Foraging capture via db8r-mcts MC-5.

        Calls POST /api/v1/foraging-strategy to get the generated portfolio,
        then replays each query via search() to capture ClaimCheck responses.

        Args:
            claim: The claim to generate queries for
            perspective: "supports_claim" or "contradicts_claim" (polarity selector)
            mode: "pregame" only (mode!="pregame" -> 501)
            replay_queries: If True, replay each query through ClaimCheck /search

        Returns:
            ForagingResult with strategy and capture results
        """
        if mode != "pregame":
            raise ValueError("Only mode='pregame' is supported (MC-5 returns 501 for other modes)")

        if perspective not in ("supports_claim", "contradicts_claim"):
            raise ValueError("perspective must be 'supports_claim' or 'contradicts_claim'")

        with self._http_client(self.settings.db8r_mcts_base_url, self.settings.db8r_mcts_timeout_seconds) as client:
            payload = {
                "claim": claim,
                "mode": mode,
                "perspective": perspective,
            }

            resp = client.post("/api/v1/foraging-strategy", json=payload)
            resp.raise_for_status()
            mc5_response = resp.json()

        # Parse the strategy
        strategy_id = f"fstrat-{uuid.uuid4().hex[:12]}"

        queries: list[ForageQuery] = []
        for i, q in enumerate(mc5_response.get("queries", [])):
            query_id = f"fq-{uuid.uuid4().hex[:12]}"
            queries.append(
                ForageQuery(
                    forage_query_id=query_id,
                    pool=q.get("pool", ""),
                    query=q.get("query", ""),
                    strategy=q.get("strategy", ""),
                    priority=q.get("priority", 0.0),
                    rank=q.get("rank", i + 1),
                    providers=q.get("providers", []),
                    intent_label=q.get("intent_label"),
                    rationale=q.get("rationale"),
                    retrieval_role=q.get("retrieval_role"),
                    scheme=q.get("scheme"),
                    critical_question_family=q.get("critical_question_family"),
                    target_schema_need_id=q.get("target_schema_need_id"),
                )
            )

        strategy = ForageStrategy(
            forage_strategy_id=strategy_id,
            claim=claim,
            mode=mode,
            perspective=perspective,
            generator_version=mc5_response.get("generator_version", ""),
            generator=mc5_response.get("generator"),
            claim_type=mc5_response.get("claim_type"),
            providers=mc5_response.get("providers", []),
            queries=queries,
            captured_at=self._now_iso(),
            fallback_reason=mc5_response.get("fallback_reason"),
            claim_decomposition=mc5_response.get("claim_decomposition"),
            polarity_reversal=mc5_response.get("polarity_reversal"),
            schema_plan=mc5_response.get("schema_plan"),
        )

        # Replay each query through ClaimCheck /search
        capture_results: list[CaptureResult] = []

        if replay_queries:
            for fq in queries:
                try:
                    result = self.search(
                        query=fq.query,
                        providers=fq.providers if fq.providers else None,
                        forage_strategy_id=strategy_id,
                        forage_query_id=fq.forage_query_id,
                    )
                    fq.fixture_id = result.fixture_id
                    capture_results.append(result)
                except Exception as e:
                    # Log but continue - some queries may fail
                    print(f"Warning: Failed to capture query '{fq.query}': {e}")

        return ForagingResult(strategy=strategy, capture_results=capture_results)

    def check_services(self) -> dict[str, bool]:
        """Check if ClaimCheck and db8r-mcts services are up."""
        status = {"claimcheck": False, "db8r_mcts": False}

        try:
            with self._http_client(self.settings.claimcheck_base_url, 5.0) as client:
                resp = client.get("/health")
                status["claimcheck"] = resp.status_code == 200
        except Exception:
            pass

        try:
            with self._http_client(self.settings.db8r_mcts_base_url, 5.0) as client:
                # db8r-mcts health is at /api/v1/health
                resp = client.get("/api/v1/health")
                status["db8r_mcts"] = resp.status_code == 200
        except Exception:
            pass

        return status
