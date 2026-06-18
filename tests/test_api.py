"""Integration tests for the annotation API."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from eval_utility.api.dependencies import get_fixtures_dir, get_store
from eval_utility.server import app
from eval_utility.store import GoldStore


@pytest.fixture
def temp_dirs():
    """Create temporary directories for fixtures and gold store."""
    with tempfile.TemporaryDirectory() as fixtures_dir:
        with tempfile.TemporaryDirectory() as gold_dir:
            yield Path(fixtures_dir), Path(gold_dir)


@pytest.fixture
def test_store(temp_dirs):
    """Create a test store."""
    _, gold_dir = temp_dirs
    db_path = gold_dir / "test_gold.db"
    return GoldStore(db_path=db_path)


@pytest.fixture
def test_fixture(temp_dirs):
    """Create a test fixture file."""
    fixtures_dir, _ = temp_dirs
    fixture_data = {
        "fixture_id": "fix-test123",
        "capture_mode": "search_A",
        "query": "test query",
        "job_id": "job-123",
        "claimcheck_version": "1.0.0",
        "captured_at": "2024-01-01T00:00:00Z",
        "schema_version": "fixture_v1",
        "documents": [
            {
                "document_id": "doc-001",
                "source_url": "https://example.com/article",
                "source_title": "Test Article",
                "source_domain": "example.com",
                "provider": "test_provider",
                "content_type": "text/html",
                "fetched_at": "2024-01-01T00:00:00Z",
                "source_reliability": 0.9,
                "retrieval_rank": 1,
                "source_text": "This is the source text for testing span offsets.",
                "source_text_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "source_text_char_len": 51,
                "extraction_status": {
                    "partial_extraction": False,
                    "chunks_processed": 1,
                    "chunks_total": 1,
                    "tokens_used": 100,
                    "token_budget": 1000,
                    "warnings": [],
                },
                "validation_warnings": [],
            }
        ],
        "spans": [
            {
                "claim_id": "claim-001",
                "document_id": "doc-001",
                "text": "source text",
                "char_offset": 12,
                "char_length": 11,
                "extraction_fidelity": 0.95,
                "match_method": "exact",
                "verbatim_span": "source text",
            }
        ],
        "retrieval_results": [
            {
                "document_id": "doc-001",
                "url": "https://example.com/article",
                "title": "Test Article",
                "rank": 1,
                "provider": "test_provider",
                "relevance_score": 0.85,
                "status": "success",
            }
        ],
    }
    # Fix the hash to match the actual source_text
    import hashlib

    source_text = fixture_data["documents"][0]["source_text"]
    fixture_data["documents"][0]["source_text_hash"] = hashlib.sha256(source_text.encode()).hexdigest()

    fixture_path = fixtures_dir / "fix-test123.json"
    with open(fixture_path, "w") as f:
        json.dump(fixture_data, f)

    return fixture_data


@pytest.fixture
def client(temp_dirs, test_store, test_fixture):
    """Create a test client with dependency overrides."""
    fixtures_dir, _ = temp_dirs

    def override_get_store():
        return test_store

    def override_get_fixtures_dir():
        return fixtures_dir

    app.dependency_overrides[get_store] = override_get_store
    app.dependency_overrides[get_fixtures_dir] = override_get_fixtures_dir

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


class TestHealth:
    """Health endpoint tests."""

    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "0.1.0"


class TestClaims:
    """Claim CRUD tests."""

    def test_create_claim(self, client):
        response = client.post(
            "/api/v1/claims",
            json={"text": "Climate change is real", "family": "factual", "split": "train"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["text"] == "Climate change is real"
        assert data["family"] == "factual"
        assert data["split"] == "train"
        assert data["claim_id"].startswith("claim-")

    def test_list_claims(self, client):
        # Create a claim first
        client.post("/api/v1/claims", json={"text": "Test claim"})

        response = client.get("/api/v1/claims")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert len(data["claims"]) >= 1

    def test_get_claim(self, client):
        # Create a claim first
        create_response = client.post("/api/v1/claims", json={"text": "Test claim"})
        claim_id = create_response.json()["claim_id"]

        response = client.get(f"/api/v1/claims/{claim_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["claim_id"] == claim_id
        assert data["text"] == "Test claim"

    def test_get_claim_not_found(self, client):
        response = client.get("/api/v1/claims/nonexistent")
        assert response.status_code == 404

    def test_update_claim(self, client):
        # Create a claim first
        create_response = client.post("/api/v1/claims", json={"text": "Original text"})
        claim_id = create_response.json()["claim_id"]

        response = client.put(f"/api/v1/claims/{claim_id}", json={"text": "Updated text"})
        assert response.status_code == 200
        data = response.json()
        assert data["text"] == "Updated text"

    def test_delete_claim(self, client):
        # Create a claim first
        create_response = client.post("/api/v1/claims", json={"text": "To be deleted"})
        claim_id = create_response.json()["claim_id"]

        response = client.delete(f"/api/v1/claims/{claim_id}")
        assert response.status_code == 204

        # Verify it's gone
        response = client.get(f"/api/v1/claims/{claim_id}")
        assert response.status_code == 404

    def test_link_document_to_claim(self, client):
        # Create a claim first
        create_response = client.post("/api/v1/claims", json={"text": "Test claim"})
        claim_id = create_response.json()["claim_id"]

        response = client.post(
            f"/api/v1/claims/{claim_id}/documents",
            json={"document_id": "doc-hash-123", "origin": "manual"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["claim_id"] == claim_id
        assert data["document_id"] == "doc-hash-123"

    def test_list_claim_documents(self, client):
        # Create a claim and link a document
        create_response = client.post("/api/v1/claims", json={"text": "Test claim"})
        claim_id = create_response.json()["claim_id"]
        client.post(
            f"/api/v1/claims/{claim_id}/documents",
            json={"document_id": "doc-hash-123", "origin": "manual"},
        )

        response = client.get(f"/api/v1/claims/{claim_id}/documents")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["document_id"] == "doc-hash-123"


class TestFixtures:
    """Fixture endpoint tests."""

    def test_list_fixtures(self, client):
        response = client.get("/api/v1/fixtures")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert len(data["fixtures"]) >= 1
        assert data["fixtures"][0]["fixture_id"] == "fix-test123"

    def test_get_fixture(self, client):
        response = client.get("/api/v1/fixtures/fix-test123")
        assert response.status_code == 200
        data = response.json()
        assert data["fixture_id"] == "fix-test123"
        assert data["capture_mode"] == "search_A"
        assert len(data["documents"]) == 1
        assert len(data["spans"]) == 1

    def test_get_fixture_not_found(self, client):
        response = client.get("/api/v1/fixtures/nonexistent")
        assert response.status_code == 404

    def test_get_fixture_document(self, client):
        response = client.get("/api/v1/fixtures/fix-test123/documents/doc-001")
        assert response.status_code == 200
        data = response.json()
        assert data["document_id"] == "doc-001"
        assert "source_text" in data  # Detail view includes source_text


class TestSpans:
    """Gold span CRUD tests."""

    def test_create_span(self, client, test_fixture):
        doc_hash = test_fixture["documents"][0]["source_text_hash"]
        response = client.post(
            "/api/v1/spans",
            json={
                "document_id": doc_hash,
                "fixture_id": "fix-test123",
                "char_offset": 0,
                "char_length": 4,
                "text": "This",
                "label_source": "human_authored",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["document_id"] == doc_hash
        assert data["char_offset"] == 0
        assert data["char_length"] == 4
        assert data["span_id"].startswith("span-")

    def test_list_spans(self, client, test_fixture):
        doc_hash = test_fixture["documents"][0]["source_text_hash"]
        # Create a span first
        client.post(
            "/api/v1/spans",
            json={
                "document_id": doc_hash,
                "fixture_id": "fix-test123",
                "char_offset": 0,
                "char_length": 4,
                "text": "This",
            },
        )

        response = client.get("/api/v1/spans")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1

    def test_get_span(self, client, test_fixture):
        doc_hash = test_fixture["documents"][0]["source_text_hash"]
        create_response = client.post(
            "/api/v1/spans",
            json={
                "document_id": doc_hash,
                "fixture_id": "fix-test123",
                "char_offset": 0,
                "char_length": 4,
                "text": "This",
            },
        )
        span_id = create_response.json()["span_id"]

        response = client.get(f"/api/v1/spans/{span_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["span_id"] == span_id

    def test_update_span(self, client, test_fixture):
        doc_hash = test_fixture["documents"][0]["source_text_hash"]
        create_response = client.post(
            "/api/v1/spans",
            json={
                "document_id": doc_hash,
                "fixture_id": "fix-test123",
                "char_offset": 0,
                "char_length": 4,
                "text": "This",
            },
        )
        span_id = create_response.json()["span_id"]

        response = client.put(f"/api/v1/spans/{span_id}", json={"is_claim_bearing": True})
        assert response.status_code == 200
        data = response.json()
        assert data["is_claim_bearing"] is True

    def test_delete_span(self, client, test_fixture):
        doc_hash = test_fixture["documents"][0]["source_text_hash"]
        create_response = client.post(
            "/api/v1/spans",
            json={
                "document_id": doc_hash,
                "fixture_id": "fix-test123",
                "char_offset": 0,
                "char_length": 4,
                "text": "This",
            },
        )
        span_id = create_response.json()["span_id"]

        response = client.delete(f"/api/v1/spans/{span_id}")
        assert response.status_code == 204

        # Verify it's gone
        response = client.get(f"/api/v1/spans/{span_id}")
        assert response.status_code == 404


class TestSpanPrefill:
    """Span prefill endpoint tests."""

    def test_prefill_spans(self, client, test_fixture):
        doc_hash = test_fixture["documents"][0]["source_text_hash"]
        response = client.post(
            "/api/v1/spans/prefill",
            json={
                "fixture_id": "fix-test123",
                "document_id": doc_hash,
                "label_source": "pipeline_prefill",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["created_count"] == 1
        assert data["skipped_count"] == 0
        assert len(data["spans"]) == 1
        assert data["spans"][0]["label_source"] == "pipeline_prefill"
        assert data["spans"][0]["is_claim_bearing"] is None  # To be annotated

    def test_prefill_spans_skip_duplicates(self, client, test_fixture):
        doc_hash = test_fixture["documents"][0]["source_text_hash"]

        # First prefill
        client.post(
            "/api/v1/spans/prefill",
            json={"fixture_id": "fix-test123", "document_id": doc_hash},
        )

        # Second prefill should skip
        response = client.post(
            "/api/v1/spans/prefill",
            json={"fixture_id": "fix-test123", "document_id": doc_hash},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["created_count"] == 0
        assert data["skipped_count"] == 1

    def test_prefill_fixture_not_found(self, client):
        response = client.post(
            "/api/v1/spans/prefill",
            json={"fixture_id": "nonexistent", "document_id": "hash123"},
        )
        assert response.status_code == 404


class TestLabels:
    """Claim-span label tests."""

    def test_create_label(self, client, test_fixture):
        # Create claim and span first
        claim_response = client.post("/api/v1/claims", json={"text": "Test claim"})
        claim_id = claim_response.json()["claim_id"]

        doc_hash = test_fixture["documents"][0]["source_text_hash"]
        span_response = client.post(
            "/api/v1/spans",
            json={
                "document_id": doc_hash,
                "fixture_id": "fix-test123",
                "char_offset": 0,
                "char_length": 4,
                "text": "This",
            },
        )
        span_id = span_response.json()["span_id"]

        response = client.post(
            "/api/v1/labels",
            json={
                "claim_id": claim_id,
                "span_id": span_id,
                "relevant_to_claim": True,
                "stance": "PRO",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["claim_id"] == claim_id
        assert data["span_id"] == span_id
        assert data["relevant_to_claim"] is True
        assert data["stance"] == "PRO"

    def test_update_label(self, client, test_fixture):
        # Create claim, span, and label
        claim_response = client.post("/api/v1/claims", json={"text": "Test claim"})
        claim_id = claim_response.json()["claim_id"]

        doc_hash = test_fixture["documents"][0]["source_text_hash"]
        span_response = client.post(
            "/api/v1/spans",
            json={
                "document_id": doc_hash,
                "fixture_id": "fix-test123",
                "char_offset": 0,
                "char_length": 4,
                "text": "This",
            },
        )
        span_id = span_response.json()["span_id"]

        client.post(
            "/api/v1/labels",
            json={"claim_id": claim_id, "span_id": span_id, "relevant_to_claim": True},
        )

        response = client.put(
            f"/api/v1/labels/{claim_id}/{span_id}",
            json={"stance": "CON"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["stance"] == "CON"

    def test_delete_label(self, client, test_fixture):
        # Create claim, span, and label
        claim_response = client.post("/api/v1/claims", json={"text": "Test claim"})
        claim_id = claim_response.json()["claim_id"]

        doc_hash = test_fixture["documents"][0]["source_text_hash"]
        span_response = client.post(
            "/api/v1/spans",
            json={
                "document_id": doc_hash,
                "fixture_id": "fix-test123",
                "char_offset": 0,
                "char_length": 4,
                "text": "This",
            },
        )
        span_id = span_response.json()["span_id"]

        client.post("/api/v1/labels", json={"claim_id": claim_id, "span_id": span_id})

        response = client.delete(f"/api/v1/labels/{claim_id}/{span_id}")
        assert response.status_code == 204

    def test_batch_labels(self, client, test_fixture):
        # Create claim and spans
        claim_response = client.post("/api/v1/claims", json={"text": "Test claim"})
        claim_id = claim_response.json()["claim_id"]

        doc_hash = test_fixture["documents"][0]["source_text_hash"]
        span1_response = client.post(
            "/api/v1/spans",
            json={
                "document_id": doc_hash,
                "fixture_id": "fix-test123",
                "char_offset": 0,
                "char_length": 4,
                "text": "This",
            },
        )
        span1_id = span1_response.json()["span_id"]

        span2_response = client.post(
            "/api/v1/spans",
            json={
                "document_id": doc_hash,
                "fixture_id": "fix-test123",
                "char_offset": 5,
                "char_length": 2,
                "text": "is",
            },
        )
        span2_id = span2_response.json()["span_id"]

        response = client.post(
            "/api/v1/labels/batch",
            json={
                "labels": [
                    {"claim_id": claim_id, "span_id": span1_id, "relevant_to_claim": True},
                    {"claim_id": claim_id, "span_id": span2_id, "relevant_to_claim": False},
                ]
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["created_count"] == 2
        assert data["updated_count"] == 0


class TestJudgments:
    """Retrieval judgment tests."""

    def test_create_judgment(self, client, test_fixture):
        # Create claim first
        claim_response = client.post("/api/v1/claims", json={"text": "Test claim"})
        claim_id = claim_response.json()["claim_id"]

        doc_hash = test_fixture["documents"][0]["source_text_hash"]
        response = client.post(
            "/api/v1/judgments",
            json={
                "claim_id": claim_id,
                "document_id": doc_hash,
                "relevant": 1,
                "retrieval_rank": 1,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["claim_id"] == claim_id
        assert data["document_id"] == doc_hash
        assert data["relevant"] == 1

    def test_update_judgment(self, client, test_fixture):
        # Create claim and judgment
        claim_response = client.post("/api/v1/claims", json={"text": "Test claim"})
        claim_id = claim_response.json()["claim_id"]

        doc_hash = test_fixture["documents"][0]["source_text_hash"]
        client.post(
            "/api/v1/judgments",
            json={"claim_id": claim_id, "document_id": doc_hash, "relevant": 1},
        )

        response = client.put(
            f"/api/v1/judgments/{claim_id}/{doc_hash}",
            json={"relevant": 0},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["relevant"] == 0

    def test_delete_judgment(self, client, test_fixture):
        # Create claim and judgment
        claim_response = client.post("/api/v1/claims", json={"text": "Test claim"})
        claim_id = claim_response.json()["claim_id"]

        doc_hash = test_fixture["documents"][0]["source_text_hash"]
        client.post(
            "/api/v1/judgments",
            json={"claim_id": claim_id, "document_id": doc_hash, "relevant": 1},
        )

        response = client.delete(f"/api/v1/judgments/{claim_id}/{doc_hash}")
        assert response.status_code == 204

    def test_batch_judgments(self, client, test_fixture):
        # Create claim
        claim_response = client.post("/api/v1/claims", json={"text": "Test claim"})
        claim_id = claim_response.json()["claim_id"]

        response = client.post(
            "/api/v1/judgments/batch",
            json={
                "judgments": [
                    {"claim_id": claim_id, "document_id": "doc-hash-1", "relevant": 1},
                    {"claim_id": claim_id, "document_id": "doc-hash-2", "relevant": 0},
                ]
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["created_count"] == 2


class TestDocuments:
    """Document annotation tests."""

    def test_upsert_document_annotation(self, client, test_fixture):
        doc_hash = test_fixture["documents"][0]["source_text_hash"]
        response = client.put(
            f"/api/v1/documents/{doc_hash}?fixture_id=fix-test123",
            json={
                "exhaustively_annotated": True,
                "lost_evidence_flag": False,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["document_id"] == doc_hash
        assert data["exhaustively_annotated"] is True

    def test_get_document_annotation(self, client, test_fixture):
        doc_hash = test_fixture["documents"][0]["source_text_hash"]
        # Create annotation first
        client.put(
            f"/api/v1/documents/{doc_hash}?fixture_id=fix-test123",
            json={"exhaustively_annotated": True},
        )

        response = client.get(f"/api/v1/documents/{doc_hash}")
        assert response.status_code == 200
        data = response.json()
        assert data["document_id"] == doc_hash

    def test_list_document_spans(self, client, test_fixture):
        doc_hash = test_fixture["documents"][0]["source_text_hash"]
        # Create a span
        client.post(
            "/api/v1/spans",
            json={
                "document_id": doc_hash,
                "fixture_id": "fix-test123",
                "char_offset": 0,
                "char_length": 4,
                "text": "This",
            },
        )

        response = client.get(f"/api/v1/documents/{doc_hash}/spans")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1


class TestDataset:
    """Dataset metadata tests."""

    def test_get_dataset(self, client):
        response = client.get("/api/v1/dataset")
        assert response.status_code == 200
        data = response.json()
        assert "dataset_version" in data
        assert "schema_version" in data
        assert "record_counts" in data

    def test_update_dataset(self, client):
        response = client.put(
            "/api/v1/dataset",
            json={"dataset_version": "v2.0", "annotation_guidelines_version": "1.0"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["dataset_version"] == "v2.0"
        assert data["annotation_guidelines_version"] == "1.0"


class TestForaging:
    """Foraging endpoint tests."""

    def test_list_strategies_empty(self, client):
        response = client.get("/api/v1/foraging/strategies")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["strategies"] == []

    def test_list_queries_empty(self, client):
        response = client.get("/api/v1/foraging/queries")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["queries"] == []

    def test_get_strategy_not_found(self, client):
        response = client.get("/api/v1/foraging/strategies/nonexistent")
        assert response.status_code == 404
