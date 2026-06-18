"""Tests for EU-3 fixture loader."""

import json

import pytest

from eval_utility.fixtures import (
    source_text_hash,
    load_fixture,
    load_all_fixtures,
    list_fixtures,
    LoadedDocument,
    LoadedSpan,
    FixtureIntegrityError,
)


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


class TestLoadedDocument:
    """Test LoadedDocument hash verification."""

    def test_verify_hash_correct(self):
        text = "Test content"
        doc = LoadedDocument(
            document_id="doc-1",
            source_url="https://example.com",
            source_title="Test",
            source_domain="example.com",
            provider="test",
            content_type="html",
            fetched_at=None,
            source_reliability=0.8,
            retrieval_rank=1,
            source_text=text,
            source_text_hash=source_text_hash(text),
            source_text_char_len=len(text),
        )
        assert doc.verify_hash()

    def test_verify_hash_incorrect(self):
        doc = LoadedDocument(
            document_id="doc-1",
            source_url="https://example.com",
            source_title="Test",
            source_domain="example.com",
            provider="test",
            content_type="html",
            fetched_at=None,
            source_reliability=0.8,
            retrieval_rank=1,
            source_text="Actual text",
            source_text_hash="wrong_hash",
            source_text_char_len=11,
        )
        assert not doc.verify_hash()


class TestLoadedSpan:
    """Test LoadedSpan verification."""

    def test_verify_against_source_correct(self):
        source_text = "The Earth is old."
        span = LoadedSpan(
            claim_id="clm-1",
            document_id="doc-1",
            text="The Earth is old.",
            char_offset=0,
            char_length=17,
            verbatim_span="The Earth is old.",
        )
        assert span.verify_against_source(source_text)

    def test_verify_against_source_incorrect(self):
        source_text = "The Earth is old."
        span = LoadedSpan(
            claim_id="clm-1",
            document_id="doc-1",
            text="The Earth is old.",
            char_offset=0,
            char_length=17,
            verbatim_span="Wrong text",
        )
        assert not span.verify_against_source(source_text)

    def test_verify_against_source_no_verbatim(self):
        span = LoadedSpan(
            claim_id="clm-1",
            document_id="doc-1",
            text="The Earth is old.",
            char_offset=0,
            char_length=17,
            verbatim_span=None,
        )
        assert not span.verify_against_source("any text")


class TestLoadFixture:
    """Test fixture loading and validation."""

    @pytest.fixture
    def valid_fixture_data(self):
        text = "The Earth is approximately 4.5 billion years old."
        return {
            "fixture_id": "fix-test123",
            "capture_mode": "extract_B",
            "query": None,
            "job_id": "esj-456",
            "claimcheck_version": None,
            "captured_at": "2026-06-17T00:00:00Z",
            "schema_version": "gold_v1",
            "documents": [
                {
                    "document_id": "doc-1",
                    "source_url": "https://example.com/test",
                    "source_title": "Test",
                    "source_domain": "example.com",
                    "provider": "test",
                    "content_type": "html",
                    "fetched_at": None,
                    "source_reliability": 0.8,
                    "retrieval_rank": 1,
                    "source_text": text,
                    "source_text_hash": source_text_hash(text),
                    "source_text_char_len": len(text),
                    "extraction_status": {
                        "partial_extraction": False,
                        "chunks_processed": 1,
                        "chunks_total": 1,
                    },
                }
            ],
            "spans": [
                {
                    "claim_id": "clm-1",
                    "document_id": "doc-1",
                    "text": "The Earth is approximately 4.5 billion years old.",
                    "char_offset": 0,
                    "char_length": 49,
                    "extraction_fidelity": 1.0,
                    "match_method": "exact",
                    "verbatim_span": "The Earth is approximately 4.5 billion years old.",
                }
            ],
            "retrieval_results": [],
        }

    def test_load_valid_fixture(self, tmp_path, valid_fixture_data):
        fixture_path = tmp_path / "fix-test123.json"
        with open(fixture_path, "w") as f:
            json.dump(valid_fixture_data, f)

        fixture = load_fixture(fixture_path)

        assert fixture.fixture_id == "fix-test123"
        assert fixture.capture_mode == "extract_B"
        assert len(fixture.documents) == 1
        assert len(fixture.spans) == 1
        assert fixture.documents[0].source_text_hash == source_text_hash(
            "The Earth is approximately 4.5 billion years old."
        )

    def test_load_fixture_with_indexes(self, tmp_path, valid_fixture_data):
        fixture_path = tmp_path / "fix-test123.json"
        with open(fixture_path, "w") as f:
            json.dump(valid_fixture_data, f)

        fixture = load_fixture(fixture_path)

        # Test indexed lookups
        doc = fixture.get_document("doc-1")
        assert doc is not None
        assert doc.document_id == "doc-1"

        doc_by_hash = fixture.get_document_by_hash(doc.source_text_hash)
        assert doc_by_hash is not None
        assert doc_by_hash.document_id == "doc-1"

        spans = fixture.get_spans_for_document("doc-1")
        assert len(spans) == 1

    def test_load_fixture_hash_mismatch(self, tmp_path, valid_fixture_data):
        # Corrupt the hash
        valid_fixture_data["documents"][0]["source_text_hash"] = "wrong_hash"

        fixture_path = tmp_path / "fix-test123.json"
        with open(fixture_path, "w") as f:
            json.dump(valid_fixture_data, f)

        with pytest.raises(FixtureIntegrityError, match="hash mismatch"):
            load_fixture(fixture_path, verify_hashes=True)

    def test_load_fixture_skip_hash_verification(self, tmp_path, valid_fixture_data):
        # Corrupt the hash
        valid_fixture_data["documents"][0]["source_text_hash"] = "wrong_hash"

        fixture_path = tmp_path / "fix-test123.json"
        with open(fixture_path, "w") as f:
            json.dump(valid_fixture_data, f)

        # Should not raise when verification disabled
        fixture = load_fixture(fixture_path, verify_hashes=False)
        assert fixture.fixture_id == "fix-test123"

    def test_load_fixture_verbatim_mismatch(self, tmp_path, valid_fixture_data):
        # Corrupt the verbatim_span
        valid_fixture_data["spans"][0]["verbatim_span"] = "Wrong text"

        fixture_path = tmp_path / "fix-test123.json"
        with open(fixture_path, "w") as f:
            json.dump(valid_fixture_data, f)

        with pytest.raises(FixtureIntegrityError, match="verbatim mismatch"):
            load_fixture(fixture_path, verify_spans=True)

    def test_load_fixture_partial_extraction(self, tmp_path, valid_fixture_data):
        valid_fixture_data["documents"][0]["extraction_status"]["partial_extraction"] = True

        fixture_path = tmp_path / "fix-test123.json"
        with open(fixture_path, "w") as f:
            json.dump(valid_fixture_data, f)

        fixture = load_fixture(fixture_path)
        assert fixture.has_partial_extraction()


class TestListFixtures:
    """Test fixture listing."""

    def test_list_fixtures(self, tmp_path):
        # Create some fixture files
        (tmp_path / "fix-001.json").write_text("{}")
        (tmp_path / "fix-002.json").write_text("{}")
        (tmp_path / "other.json").write_text("{}")  # Should not be listed

        fixtures = list_fixtures(tmp_path)

        assert len(fixtures) == 2
        assert all(p.name.startswith("fix-") for p in fixtures)

    def test_list_fixtures_empty_dir(self, tmp_path):
        fixtures = list_fixtures(tmp_path)
        assert fixtures == []

    def test_list_fixtures_nonexistent_dir(self, tmp_path):
        fixtures = list_fixtures(tmp_path / "nonexistent")
        assert fixtures == []


class TestLoadAllFixtures:
    """Test loading all fixtures from a directory."""

    def test_load_all_fixtures(self, tmp_path):
        text = "Test text"
        fixture_data = {
            "fixture_id": "fix-001",
            "capture_mode": "extract_B",
            "query": None,
            "job_id": "esj-1",
            "claimcheck_version": None,
            "captured_at": "2026-06-17T00:00:00Z",
            "schema_version": "gold_v1",
            "documents": [
                {
                    "document_id": "doc-1",
                    "source_url": "https://example.com",
                    "source_text": text,
                    "source_text_hash": source_text_hash(text),
                    "source_text_char_len": len(text),
                }
            ],
            "spans": [],
            "retrieval_results": [],
        }

        # Create two valid fixtures
        for i in range(2):
            data = fixture_data.copy()
            data["fixture_id"] = f"fix-00{i+1}"
            with open(tmp_path / f"fix-00{i+1}.json", "w") as f:
                json.dump(data, f)

        fixtures = load_all_fixtures(tmp_path)
        assert len(fixtures) == 2

    def test_load_all_fixtures_skip_errors(self, tmp_path):
        # Create one valid and one invalid fixture
        text = "Test text"
        valid = {
            "fixture_id": "fix-001",
            "capture_mode": "extract_B",
            "documents": [
                {
                    "document_id": "doc-1",
                    "source_text": text,
                    "source_text_hash": source_text_hash(text),
                    "source_text_char_len": len(text),
                }
            ],
            "spans": [],
            "retrieval_results": [],
        }
        invalid = {"fixture_id": "fix-002", "documents": [{"source_text_hash": "bad"}]}

        with open(tmp_path / "fix-001.json", "w") as f:
            json.dump(valid, f)
        with open(tmp_path / "fix-002.json", "w") as f:
            json.dump(invalid, f)

        # Should load one, skip one
        fixtures = load_all_fixtures(tmp_path, skip_errors=True)
        assert len(fixtures) == 1
        assert fixtures[0].fixture_id == "fix-001"
