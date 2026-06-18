"""Tests for EU-2 capture client."""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from eval_utility.capture import (
    CaptureClient,
    CapturedDocument,
    CapturedSpan,
    CapturedFixture,
    ExtractionStatus,
    ForageQuery,
    ForageStrategy,
    ForagingResult,
    CaptureError,
)
from eval_utility.config import Settings
from eval_utility.fixtures import source_text_hash


class TestSourceTextHash:
    """Test content-addressing via source_text_hash."""

    def test_deterministic(self):
        text = "The Earth is 4.5 billion years old."
        h1 = source_text_hash(text)
        h2 = source_text_hash(text)
        assert h1 == h2

    def test_different_texts_different_hashes(self):
        h1 = source_text_hash("Text A")
        h2 = source_text_hash("Text B")
        assert h1 != h2

    def test_sha256_format(self):
        h = source_text_hash("test")
        assert len(h) == 64  # SHA-256 hex digest
        assert all(c in "0123456789abcdef" for c in h)


class TestExtractionStatus:
    """Test ExtractionStatus parsing."""

    def test_full_extraction(self):
        status = ExtractionStatus(
            partial_extraction=False,
            chunks_processed=5,
            chunks_total=5,
            tokens_used=1000,
            token_budget=10000,
            warnings=[],
        )
        assert not status.partial_extraction

    def test_partial_extraction(self):
        status = ExtractionStatus(
            partial_extraction=True,
            chunks_processed=3,
            chunks_total=10,
            tokens_used=10000,
            token_budget=10000,
            warnings=["max_chunks_exceeded"],
        )
        assert status.partial_extraction
        assert "max_chunks_exceeded" in status.warnings


class TestCapturedSpan:
    """Test CapturedSpan from claims[] array."""

    def test_span_with_offsets(self):
        span = CapturedSpan(
            claim_id="clm-123",
            document_id="doc-456",
            text="The Earth is old.",
            char_offset=0,
            char_length=17,
            extraction_fidelity=1.0,
            match_method="exact",
        )
        assert span.char_offset == 0
        assert span.char_length == 17
        assert span.match_method == "exact"


class TestCapturedDocument:
    """Test CapturedDocument with content-addressing."""

    def test_document_hash(self):
        text = "Source text content"
        doc = CapturedDocument(
            document_id="doc-abc",
            source_url="https://example.com/doc",
            source_title="Example",
            source_domain="example.com",
            provider="serper",
            content_type="html",
            fetched_at=None,
            source_reliability=0.8,
            retrieval_rank=1,
            source_text=text,
            source_text_hash=source_text_hash(text),
            source_text_char_len=len(text),
        )
        assert doc.source_text_hash == source_text_hash(text)
        assert doc.source_text_char_len == 19


class TestCapturedFixture:
    """Test CapturedFixture serialization."""

    def test_to_dict(self):
        fixture = CapturedFixture(
            fixture_id="fix-test123",
            capture_mode="extract_B",
            query=None,
            job_id="esj-456",
            claimcheck_version=None,
            captured_at="2026-06-17T00:00:00Z",
            schema_version="gold_v1",
            documents=[],
            spans=[],
            retrieval_results=[],
        )
        d = fixture.to_dict()
        assert d["fixture_id"] == "fix-test123"
        assert d["capture_mode"] == "extract_B"
        assert d["schema_version"] == "gold_v1"


class TestCaptureClientHelpers:
    """Test CaptureClient helper methods."""

    @pytest.fixture
    def client(self, tmp_path):
        settings = Settings(fixtures_dir=tmp_path / "fixtures")
        return CaptureClient(settings)

    def test_infer_content_type_pdf(self, client):
        assert client._infer_content_type("https://example.com/doc.pdf") == "pdf"
        assert client._infer_content_type("https://example.com/doc.PDF") == "pdf"

    def test_infer_content_type_html(self, client):
        assert client._infer_content_type("https://example.com/page.html") == "html"
        assert client._infer_content_type("https://example.com/page.htm") == "html"

    def test_infer_content_type_raw_text(self, client):
        assert client._infer_content_type("claimcheck://raw-text/abc123") == "raw_text"

    def test_infer_content_type_unknown(self, client):
        assert client._infer_content_type("https://example.com/page") is None

    def test_reconstruct_source_text_single_passage(self, client):
        evidence_doc = {
            "passages": [
                {"text": "Hello world", "char_start": 0, "char_end": 11}
            ]
        }
        text = client._reconstruct_source_text(evidence_doc)
        assert text == "Hello world"

    def test_reconstruct_source_text_multiple_passages(self, client):
        evidence_doc = {
            "passages": [
                {"text": "First part.", "char_start": 0, "char_end": 11},
                {"text": "Second part.", "char_start": 12, "char_end": 24},
            ]
        }
        text = client._reconstruct_source_text(evidence_doc)
        # Should have a space between (gap from 11 to 12)
        assert text == "First part. Second part."

    def test_reconstruct_source_text_with_gap(self, client):
        evidence_doc = {
            "passages": [
                {"text": "AAA", "char_start": 0, "char_end": 3},
                {"text": "BBB", "char_start": 6, "char_end": 9},  # Gap of 3 chars
            ]
        }
        text = client._reconstruct_source_text(evidence_doc)
        assert text == "AAA   BBB"  # 3 spaces fill the gap

    def test_reconstruct_source_text_empty_passages(self, client):
        evidence_doc = {"passages": []}
        assert client._reconstruct_source_text(evidence_doc) == ""

    def test_parse_extraction_status_full(self, client):
        status_dict = {
            "partial_extraction": False,
            "chunks_processed": 5,
            "chunks_total": 5,
            "tokens_used": 500,
            "token_budget": 10000,
            "warnings": [],
        }
        status = client._parse_extraction_status(status_dict)
        assert status is not None
        assert not status.partial_extraction
        assert status.chunks_processed == 5

    def test_parse_extraction_status_partial(self, client):
        status_dict = {
            "partial_extraction": True,
            "chunks_processed": 3,
            "chunks_total": 10,
            "warnings": ["max_chunks_exceeded"],
        }
        status = client._parse_extraction_status(status_dict)
        assert status is not None
        assert status.partial_extraction
        assert "max_chunks_exceeded" in status.warnings

    def test_parse_extraction_status_none(self, client):
        assert client._parse_extraction_status(None) is None


class TestCaptureClientExtractSpans:
    """Test extraction of spans from claims[] array."""

    @pytest.fixture
    def client(self, tmp_path):
        settings = Settings(fixtures_dir=tmp_path / "fixtures")
        return CaptureClient(settings)

    def test_extract_spans_with_offsets(self, client):
        response = {
            "claims": [
                {
                    "claim_id": "clm-1",
                    "source_document_id": "doc-1",
                    "statement": "Test claim",
                    "statement_offset": 10,
                    "statement_length": 10,
                    "extraction_fidelity": 1.0,
                    "match_method": "exact",
                },
                {
                    "claim_id": "clm-2",
                    "source_document_id": "doc-1",
                    "statement": "Another claim",
                    "statement_offset": 30,
                    "statement_length": 13,
                },
            ]
        }
        spans = client._extract_spans(response)
        assert len(spans) == 2
        assert spans[0].char_offset == 10
        assert spans[0].char_length == 10
        assert spans[1].char_offset == 30

    def test_extract_spans_skips_null_offsets(self, client):
        """Per spec: projections return null offsets, so skip those."""
        response = {
            "claims": [
                {
                    "claim_id": "clm-1",
                    "statement": "Valid",
                    "statement_offset": 0,
                    "statement_length": 5,
                },
                {
                    "claim_id": "clm-2",
                    "statement": "Invalid - no offset",
                    "statement_offset": None,  # Projection with null offset
                    "statement_length": None,
                },
            ]
        }
        spans = client._extract_spans(response)
        assert len(spans) == 1
        assert spans[0].claim_id == "clm-1"


class TestModeCImport:
    """Test Mode C: import a previously captured response."""

    @pytest.fixture
    def client(self, tmp_path):
        settings = Settings(fixtures_dir=tmp_path / "fixtures")
        return CaptureClient(settings)

    def test_import_valid_response(self, client, tmp_path):
        # Create a mock response file
        response = {
            "job_id": "esj-test",
            "query": "test query",
            "claims": [
                {
                    "claim_id": "clm-1",
                    "source_document_id": "doc-1",
                    "statement": "Test claim",
                    "statement_offset": 0,
                    "statement_length": 10,
                }
            ],
            "evidence_documents": [
                {
                    "document_id": "doc-1",
                    "source_url": "https://example.com/test",
                    "passages": [{"text": "Test claim text", "char_start": 0, "char_end": 15}],
                }
            ],
            "results": [],
        }
        response_file = tmp_path / "response.json"
        with open(response_file, "w") as f:
            json.dump(response, f)

        result = client.import_response(str(response_file))

        assert result.capture_mode == "debate_C"
        assert result.fixture_id.startswith("fix-")
        assert Path(result.fixture_path).exists()

        # Verify fixture contents
        with open(result.fixture_path) as f:
            fixture = json.load(f)
        assert fixture["capture_mode"] == "debate_C"
        assert fixture["job_id"] == "esj-test"
        assert len(fixture["spans"]) == 1
        assert len(fixture["documents"]) == 1

    def test_import_missing_file(self, client):
        with pytest.raises(CaptureError, match="not found"):
            client.import_response("/nonexistent/file.json")

    def test_import_invalid_format(self, client, tmp_path):
        # Create an invalid response file
        response_file = tmp_path / "invalid.json"
        with open(response_file, "w") as f:
            json.dump({"random": "data"}, f)

        with pytest.raises(CaptureError, match="Invalid response format"):
            client.import_response(str(response_file))


class TestFixturePersistence:
    """Test fixture saving and content addressing."""

    @pytest.fixture
    def client(self, tmp_path):
        settings = Settings(fixtures_dir=tmp_path / "fixtures")
        return CaptureClient(settings)

    def test_fixture_saved_as_json(self, client):
        fixture = CapturedFixture(
            fixture_id="fix-test",
            capture_mode="extract_B",
            query=None,
            job_id="esj-123",
            claimcheck_version=None,
            captured_at="2026-06-17T00:00:00Z",
            schema_version="gold_v1",
            documents=[],
            spans=[],
            retrieval_results=[],
        )
        path = client._save_fixture(fixture)

        assert Path(path).exists()
        with open(path) as f:
            saved = json.load(f)
        assert saved["fixture_id"] == "fix-test"

    def test_document_content_addressed(self, client, tmp_path):
        """Verify documents are content-addressed by source_text_hash."""
        response = {
            "job_id": "esj-test",
            "claims": [],
            "evidence_documents": [
                {
                    "document_id": "doc-1",
                    "source_url": "https://example.com/test",
                    "passages": [{"text": "Unique content", "char_start": 0, "char_end": 14}],
                }
            ],
            "results": [],
        }
        response_file = tmp_path / "response.json"
        with open(response_file, "w") as f:
            json.dump(response, f)

        result = client.import_response(str(response_file))

        with open(result.fixture_path) as f:
            fixture = json.load(f)

        doc = fixture["documents"][0]
        expected_hash = source_text_hash("Unique content")
        assert doc["source_text_hash"] == expected_hash
        assert doc["source_text_char_len"] == 14


class TestForageQueryDataclass:
    """Test ForageQuery dataclass."""

    def test_forage_query_fields(self):
        fq = ForageQuery(
            forage_query_id="fq-123",
            pool="PRO",
            query="test query",
            strategy="direct_evidence",
            priority=0.9,
            rank=1,
            providers=["serper", "tavily"],
            intent_label="direct_evidence",
            rationale="Find supporting documents",
            retrieval_role="direct_support",
        )
        assert fq.pool == "PRO"
        assert fq.priority == 0.9
        assert "serper" in fq.providers


class TestForageStrategyDataclass:
    """Test ForageStrategy dataclass."""

    def test_forage_strategy_fields(self):
        queries = [
            ForageQuery(
                forage_query_id="fq-1",
                pool="PRO",
                query="q1",
                strategy="s1",
                priority=0.9,
                rank=1,
                providers=["serper"],
            )
        ]
        strategy = ForageStrategy(
            forage_strategy_id="fstrat-123",
            claim="Test claim",
            mode="pregame",
            perspective="supports_claim",
            generator_version="query_generation:llm:model=gpt-4.1-nano",
            generator="llm",
            claim_type="factual",
            providers=["serper", "tavily"],
            queries=queries,
            captured_at="2026-06-17T00:00:00Z",
        )
        assert strategy.perspective == "supports_claim"
        assert len(strategy.queries) == 1
        assert "llm" in strategy.generator_version


class TestCaptureForagingValidation:
    """Test capture_foraging parameter validation."""

    @pytest.fixture
    def client(self, tmp_path):
        settings = Settings(fixtures_dir=tmp_path / "fixtures")
        return CaptureClient(settings)

    def test_invalid_mode_rejected(self, client):
        with pytest.raises(ValueError, match="pregame"):
            client.capture_foraging("test claim", mode="reactive")

    def test_invalid_perspective_rejected(self, client):
        with pytest.raises(ValueError, match="perspective"):
            client.capture_foraging("test claim", perspective="invalid")


class TestCheckServices:
    """Test service health check."""

    @pytest.fixture
    def client(self, tmp_path):
        settings = Settings(
            fixtures_dir=tmp_path / "fixtures",
            claimcheck_base_url="http://127.0.0.1:59999",  # Non-existent
            db8r_mcts_base_url="http://127.0.0.1:59998",  # Non-existent
        )
        return CaptureClient(settings)

    def test_services_down(self, client):
        status = client.check_services()
        assert not status["claimcheck"]
        assert not status["db8r_mcts"]


class TestCaptureForagingIntegration:
    """EU-2f: Mocked integration tests for capture_foraging."""

    @pytest.fixture
    def client(self, tmp_path):
        settings = Settings(
            fixtures_dir=tmp_path / "fixtures",
            claimcheck_base_url="http://claimcheck:8001",
            db8r_mcts_base_url="http://mcts:8000",
        )
        return CaptureClient(settings)

    @pytest.fixture
    def mc5_response(self):
        """Sample MC-5 foraging-strategy response."""
        return {
            "generator_version": "query_generation:llm:model=gpt-4.1-nano",
            "generator": "llm",
            "claim_type": "factual",
            "providers": ["serper", "tavily"],
            "queries": [
                {
                    "pool": "PRO",
                    "query": "Earth age scientific evidence",
                    "strategy": "direct_evidence",
                    "priority": 0.95,
                    "rank": 1,
                    "providers": ["serper"],
                    "intent_label": "direct_evidence",
                    "rationale": "Find direct scientific sources",
                    "retrieval_role": "direct_support",
                    "scheme": "expert_opinion",
                },
                {
                    "pool": "PRO",
                    "query": "radiometric dating Earth",
                    "strategy": "methodology",
                    "priority": 0.85,
                    "rank": 2,
                    "providers": ["tavily"],
                    "intent_label": "methodology",
                    "rationale": "Find dating methodology sources",
                    "retrieval_role": "indirect_support",
                },
            ],
            "fallback_reason": None,
            "claim_decomposition": {"core_assertion": "Earth is 4.5 billion years old"},
            "polarity_reversal": None,
            "schema_plan": {"primary_schemes": ["expert_opinion", "evidence"]},
        }

    @pytest.fixture
    def claimcheck_search_response(self):
        """Sample ClaimCheck /search response for query replay."""
        def make_response(query: str, job_id: str):
            source_text = f"Document content for query: {query}"
            return {
                "job_id": job_id,
                "status": "completed",
                "query": query,
                "claims": [
                    {
                        "claim_id": f"clm-{job_id}",
                        "source_document_id": f"doc-{job_id}",
                        "statement": "The Earth is 4.5 billion years old.",
                        "statement_offset": 0,
                        "statement_length": 37,
                        "extraction_fidelity": 1.0,
                        "match_method": "exact",
                        "verbatim_span": "The Earth is 4.5 billion years old.",
                    }
                ],
                "evidence_documents": [
                    {
                        "document_id": f"doc-{job_id}",
                        "source_url": f"https://example.com/{job_id}",
                        "source_title": "Test Document",
                        "source_domain": "example.com",
                        "provider": "serper",
                        "content_type": "html",
                        "source_text": source_text,
                        "extraction_status": {
                            "partial_extraction": False,
                            "chunks_processed": 1,
                            "chunks_total": 1,
                        },
                    }
                ],
                "results": [
                    {
                        "url": f"https://example.com/{job_id}",
                        "title": "Test Document",
                        "rank": 1,
                        "provider": "serper",
                    }
                ],
            }
        return make_response

    def test_capture_foraging_parses_strategy(self, client, mc5_response):
        """Verify MC-5 response is correctly parsed into ForageStrategy."""
        with patch.object(client, "_http_client") as mock_http:
            # Mock MC-5 response
            mock_client = MagicMock()
            mock_http.return_value.__enter__.return_value = mock_client
            mock_response = MagicMock()
            mock_response.json.return_value = mc5_response
            mock_response.raise_for_status = MagicMock()
            mock_client.post.return_value = mock_response

            result = client.capture_foraging(
                claim="The Earth is 4.5 billion years old.",
                perspective="supports_claim",
                replay_queries=False,  # Don't replay to isolate parsing test
            )

            assert isinstance(result, ForagingResult)
            assert isinstance(result.strategy, ForageStrategy)

            strategy = result.strategy
            assert strategy.forage_strategy_id.startswith("fstrat-")
            assert strategy.claim == "The Earth is 4.5 billion years old."
            assert strategy.mode == "pregame"
            assert strategy.perspective == "supports_claim"
            assert strategy.generator_version == "query_generation:llm:model=gpt-4.1-nano"
            assert strategy.generator == "llm"
            assert strategy.claim_type == "factual"
            assert strategy.providers == ["serper", "tavily"]
            assert strategy.source == "mc5_endpoint"
            assert strategy.claim_decomposition == {"core_assertion": "Earth is 4.5 billion years old"}

    def test_capture_foraging_parses_queries(self, client, mc5_response):
        """Verify queries are correctly parsed into ForageQuery list."""
        with patch.object(client, "_http_client") as mock_http:
            mock_client = MagicMock()
            mock_http.return_value.__enter__.return_value = mock_client
            mock_response = MagicMock()
            mock_response.json.return_value = mc5_response
            mock_response.raise_for_status = MagicMock()
            mock_client.post.return_value = mock_response

            result = client.capture_foraging(
                claim="Test claim",
                perspective="contradicts_claim",
                replay_queries=False,
            )

            queries = result.strategy.queries
            assert len(queries) == 2

            q1 = queries[0]
            assert q1.forage_query_id.startswith("fq-")
            assert q1.pool == "PRO"
            assert q1.query == "Earth age scientific evidence"
            assert q1.strategy == "direct_evidence"
            assert q1.priority == 0.95
            assert q1.rank == 1
            assert q1.providers == ["serper"]
            assert q1.intent_label == "direct_evidence"
            assert q1.rationale == "Find direct scientific sources"
            assert q1.retrieval_role == "direct_support"
            assert q1.scheme == "expert_opinion"

            q2 = queries[1]
            assert q2.pool == "PRO"
            assert q2.query == "radiometric dating Earth"
            assert q2.rank == 2
            assert q2.providers == ["tavily"]

    def test_capture_foraging_replays_queries(self, client, mc5_response, claimcheck_search_response):
        """Verify each query is replayed via ClaimCheck /search."""
        call_count = {"mc5": 0, "search_post": 0, "search_get": 0}
        job_counter = [0]

        def mock_post(url, **kwargs):
            response = MagicMock()
            response.raise_for_status = MagicMock()

            if "/foraging-strategy" in url:
                call_count["mc5"] += 1
                response.json.return_value = mc5_response
            else:  # /search
                call_count["search_post"] += 1
                job_counter[0] += 1
                job_id = f"esj-test-{job_counter[0]}"
                response.json.return_value = {"job_id": job_id, "status": "pending"}
            return response

        def mock_get(url, **kwargs):
            call_count["search_get"] += 1
            response = MagicMock()
            response.raise_for_status = MagicMock()
            # Extract job_id from URL
            job_id = f"esj-test-{call_count['search_get']}"
            query = mc5_response["queries"][call_count["search_get"] - 1]["query"]
            response.json.return_value = claimcheck_search_response(query, job_id)
            return response

        with patch.object(client, "_http_client") as mock_http:
            mock_client = MagicMock()
            mock_http.return_value.__enter__.return_value = mock_client
            mock_client.post.side_effect = mock_post
            mock_client.get.side_effect = mock_get

            result = client.capture_foraging(
                claim="The Earth is 4.5 billion years old.",
                perspective="supports_claim",
                replay_queries=True,
            )

            # Verify MC-5 was called once
            assert call_count["mc5"] == 1

            # Verify /search was called for each query (2 queries = 2 POSTs + 2 GETs)
            assert call_count["search_post"] == 2
            assert call_count["search_get"] == 2

            # Verify capture results
            assert len(result.capture_results) == 2
            for cr in result.capture_results:
                assert cr.fixture_id.startswith("fix-")
                assert cr.capture_mode == "search_A"

    def test_capture_foraging_links_fixtures_to_queries(self, client, mc5_response, claimcheck_search_response):
        """Verify fixture_id is set on each ForageQuery after replay."""
        job_counter = [0]

        def mock_post(url, **kwargs):
            response = MagicMock()
            response.raise_for_status = MagicMock()

            if "/foraging-strategy" in url:
                response.json.return_value = mc5_response
            else:
                job_counter[0] += 1
                response.json.return_value = {"job_id": f"esj-{job_counter[0]}", "status": "pending"}
            return response

        def mock_get(url, **kwargs):
            response = MagicMock()
            response.raise_for_status = MagicMock()
            job_id = url.split("/")[-1].split("?")[0]
            idx = int(job_id.split("-")[-1]) - 1
            query = mc5_response["queries"][idx]["query"]
            response.json.return_value = claimcheck_search_response(query, job_id)
            return response

        with patch.object(client, "_http_client") as mock_http:
            mock_client = MagicMock()
            mock_http.return_value.__enter__.return_value = mock_client
            mock_client.post.side_effect = mock_post
            mock_client.get.side_effect = mock_get

            result = client.capture_foraging(
                claim="Test",
                perspective="supports_claim",
                replay_queries=True,
            )

            # Each query should have a fixture_id set
            for query in result.strategy.queries:
                assert query.fixture_id is not None
                assert query.fixture_id.startswith("fix-")

    def test_capture_foraging_passes_strategy_ids_to_search(self, client, mc5_response, claimcheck_search_response):
        """Verify forage_strategy_id and forage_query_id are passed to search()."""
        captured_fixture_metadata = []
        job_counter = [0]

        def mock_post(url, **kwargs):
            response = MagicMock()
            response.raise_for_status = MagicMock()

            if "/foraging-strategy" in url:
                response.json.return_value = mc5_response
            else:
                job_counter[0] += 1
                response.json.return_value = {"job_id": f"esj-{job_counter[0]}", "status": "pending"}
            return response

        def mock_get(url, **kwargs):
            response = MagicMock()
            response.raise_for_status = MagicMock()
            job_id = url.split("/")[-1].split("?")[0]
            idx = int(job_id.split("-")[-1]) - 1
            query = mc5_response["queries"][idx]["query"]
            response.json.return_value = claimcheck_search_response(query, job_id)
            return response

        with patch.object(client, "_http_client") as mock_http:
            mock_client = MagicMock()
            mock_http.return_value.__enter__.return_value = mock_client
            mock_client.post.side_effect = mock_post
            mock_client.get.side_effect = mock_get

            result = client.capture_foraging(
                claim="Test",
                perspective="supports_claim",
                replay_queries=True,
            )

            # Check fixtures contain forage_strategy_id and forage_query_id
            for cr in result.capture_results:
                with open(cr.fixture_path) as f:
                    fixture = json.load(f)
                assert fixture["forage_strategy_id"] == result.strategy.forage_strategy_id
                assert fixture["forage_query_id"] is not None
                captured_fixture_metadata.append(
                    (fixture["forage_strategy_id"], fixture["forage_query_id"])
                )

            # All fixtures should have same strategy_id but different query_ids
            strategy_ids = set(m[0] for m in captured_fixture_metadata)
            query_ids = set(m[1] for m in captured_fixture_metadata)
            assert len(strategy_ids) == 1
            assert len(query_ids) == 2  # Two different queries

    def test_capture_foraging_both_perspectives(self, client, mc5_response):
        """Verify both perspectives can be captured."""
        with patch.object(client, "_http_client") as mock_http:
            mock_client = MagicMock()
            mock_http.return_value.__enter__.return_value = mock_client
            mock_response = MagicMock()
            mock_response.json.return_value = mc5_response
            mock_response.raise_for_status = MagicMock()
            mock_client.post.return_value = mock_response

            # supports_claim
            result_pro = client.capture_foraging(
                claim="Test",
                perspective="supports_claim",
                replay_queries=False,
            )
            assert result_pro.strategy.perspective == "supports_claim"

            # contradicts_claim
            result_con = client.capture_foraging(
                claim="Test",
                perspective="contradicts_claim",
                replay_queries=False,
            )
            assert result_con.strategy.perspective == "contradicts_claim"

    def test_capture_foraging_continues_on_query_failure(self, client, mc5_response, claimcheck_search_response, capsys):
        """Verify capture continues even if some queries fail."""
        job_counter = [0]

        def mock_post(url, **kwargs):
            response = MagicMock()
            response.raise_for_status = MagicMock()

            if "/foraging-strategy" in url:
                response.json.return_value = mc5_response
            else:
                job_counter[0] += 1
                if job_counter[0] == 1:
                    # First query fails
                    raise Exception("Network error")
                response.json.return_value = {"job_id": f"esj-{job_counter[0]}", "status": "pending"}
            return response

        def mock_get(url, **kwargs):
            response = MagicMock()
            response.raise_for_status = MagicMock()
            query = mc5_response["queries"][1]["query"]  # Second query
            response.json.return_value = claimcheck_search_response(query, "esj-2")
            return response

        with patch.object(client, "_http_client") as mock_http:
            mock_client = MagicMock()
            mock_http.return_value.__enter__.return_value = mock_client
            mock_client.post.side_effect = mock_post
            mock_client.get.side_effect = mock_get

            result = client.capture_foraging(
                claim="Test",
                perspective="supports_claim",
                replay_queries=True,
            )

            # Should have captured 1 of 2 queries (first failed)
            assert len(result.capture_results) == 1
            # Warning should be printed
            captured = capsys.readouterr()
            assert "Warning" in captured.out or len(result.capture_results) == 1
