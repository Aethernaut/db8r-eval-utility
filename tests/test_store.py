"""Tests for EU-3 gold store (SQLite)."""

import pytest

from eval_utility.store import (
    GoldStore,
    Claim,
    ClaimDocumentLink,
    DocumentAnnotation,
    GoldSpan,
    ClaimSpanLabel,
    RetrievalJudgment,
    ForageStrategyRecord,
    ForageQueryRecord,
    SCHEMA_VERSION,
)


@pytest.fixture
def store(tmp_path):
    """Create a fresh store for each test."""
    db_path = tmp_path / "test_gold.db"
    return GoldStore(db_path=db_path)


class TestGoldStoreInit:
    """Test store initialization."""

    def test_creates_db_file(self, tmp_path):
        db_path = tmp_path / "gold.db"
        GoldStore(db_path=db_path)
        assert db_path.exists()

    def test_creates_parent_dirs(self, tmp_path):
        db_path = tmp_path / "nested" / "dir" / "gold.db"
        GoldStore(db_path=db_path)
        assert db_path.exists()

    def test_initializes_schema(self, store):
        # Should be able to query tables
        counts = store.count_records()
        assert "claim" in counts
        assert "gold_span" in counts
        assert "forage_strategy" in counts

    def test_initializes_dataset_singleton(self, store):
        dataset = store.get_dataset()
        assert dataset.schema_version == SCHEMA_VERSION


class TestClaimCRUD:
    """Test claim operations."""

    def test_upsert_claim(self, store):
        claim = Claim(
            claim_id="clm-001",
            text="The Earth is 4.5 billion years old.",
            family="factual",
            proof_standard="PE",
            split="train",
        )
        result = store.upsert_claim(claim)
        assert result.claim_id == "clm-001"
        assert result.created_at != ""

    def test_get_claim(self, store):
        claim = Claim(claim_id="clm-002", text="Test claim", family="policy")
        store.upsert_claim(claim)

        retrieved = store.get_claim("clm-002")
        assert retrieved is not None
        assert retrieved.text == "Test claim"
        assert retrieved.family == "policy"

    def test_get_claim_not_found(self, store):
        assert store.get_claim("nonexistent") is None

    def test_list_claims(self, store):
        store.upsert_claim(Claim(claim_id="clm-001", text="Claim 1", family="factual", split="train"))
        store.upsert_claim(Claim(claim_id="clm-002", text="Claim 2", family="policy", split="test"))
        store.upsert_claim(Claim(claim_id="clm-003", text="Claim 3", family="factual", split="test"))

        # All claims
        all_claims = store.list_claims()
        assert len(all_claims) == 3

        # Filter by split
        test_claims = store.list_claims(split="test")
        assert len(test_claims) == 2

        # Filter by family
        factual_claims = store.list_claims(family="factual")
        assert len(factual_claims) == 2

        # Filter by both
        test_factual = store.list_claims(split="test", family="factual")
        assert len(test_factual) == 1

    def test_update_claim(self, store):
        claim = Claim(claim_id="clm-001", text="Original", family="factual")
        store.upsert_claim(claim)

        # Update
        claim.text = "Updated"
        claim.family = "policy"
        store.upsert_claim(claim)

        retrieved = store.get_claim("clm-001")
        assert retrieved.text == "Updated"
        assert retrieved.family == "policy"


class TestClaimDocumentLink:
    """Test claim-document link operations."""

    def test_upsert_link(self, store):
        # First create a claim
        store.upsert_claim(Claim(claim_id="clm-001", text="Test"))

        link = ClaimDocumentLink(
            claim_id="clm-001",
            document_id="doc-hash-123",
            origin="search",
            fixture_id="fix-001",
        )
        result = store.upsert_claim_document_link(link)
        assert result.created_at != ""

    def test_get_documents_for_claim(self, store):
        store.upsert_claim(Claim(claim_id="clm-001", text="Test"))
        store.upsert_claim_document_link(
            ClaimDocumentLink(claim_id="clm-001", document_id="doc-1", origin="search")
        )
        store.upsert_claim_document_link(
            ClaimDocumentLink(claim_id="clm-001", document_id="doc-2", origin="manual")
        )

        links = store.get_documents_for_claim("clm-001")
        assert len(links) == 2


class TestDocumentAnnotation:
    """Test document annotation operations."""

    def test_upsert_annotation(self, store):
        annotation = DocumentAnnotation(
            document_id="doc-hash-123",
            fixture_id="fix-001",
            exhaustively_annotated=True,
            lost_evidence_flag=False,
        )
        result = store.upsert_document_annotation(annotation)
        assert result.created_at != ""

    def test_get_annotation(self, store):
        store.upsert_document_annotation(
            DocumentAnnotation(
                document_id="doc-hash-123",
                fixture_id="fix-001",
                exhaustively_annotated=True,
                lost_evidence_flag=True,
                lost_evidence_note="Missing table data",
            )
        )

        retrieved = store.get_document_annotation("doc-hash-123")
        assert retrieved is not None
        assert retrieved.exhaustively_annotated is True
        assert retrieved.lost_evidence_flag is True
        assert retrieved.lost_evidence_note == "Missing table data"


class TestGoldSpan:
    """Test gold span operations."""

    def test_upsert_span(self, store):
        span = GoldSpan(
            span_id="span-001",
            document_id="doc-hash-123",
            fixture_id="fix-001",
            char_offset=0,
            char_length=50,
            text="The Earth is approximately 4.5 billion years old.",
            is_claim_bearing=True,
            label_source="pipeline_prefill_corrected",
        )
        result = store.upsert_gold_span(span)
        assert result.created_at != ""

    def test_get_span(self, store):
        store.upsert_gold_span(
            GoldSpan(
                span_id="span-001",
                document_id="doc-hash-123",
                fixture_id="fix-001",
                char_offset=0,
                char_length=50,
                text="Test span",
                is_claim_bearing=True,
            )
        )

        retrieved = store.get_gold_span("span-001")
        assert retrieved is not None
        assert retrieved.is_claim_bearing is True
        assert retrieved.char_offset == 0

    def test_get_spans_for_document(self, store):
        for i in range(3):
            store.upsert_gold_span(
                GoldSpan(
                    span_id=f"span-{i}",
                    document_id="doc-hash-123",
                    fixture_id="fix-001",
                    char_offset=i * 50,
                    char_length=40,
                    text=f"Span {i}",
                )
            )

        spans = store.get_spans_for_document("doc-hash-123")
        assert len(spans) == 3
        # Should be ordered by offset
        assert spans[0].char_offset < spans[1].char_offset < spans[2].char_offset


class TestClaimSpanLabel:
    """Test claim-span label operations."""

    def test_upsert_label(self, store):
        # Setup
        store.upsert_claim(Claim(claim_id="clm-001", text="Test"))
        store.upsert_gold_span(
            GoldSpan(
                span_id="span-001",
                document_id="doc-123",
                fixture_id="fix-001",
                char_offset=0,
                char_length=10,
                text="Test",
            )
        )

        label = ClaimSpanLabel(
            claim_id="clm-001",
            span_id="span-001",
            relevant_to_claim=True,
            stance="PRO",
            strength_ordinal="moderate",
        )
        result = store.upsert_claim_span_label(label)
        assert result.created_at != ""

    def test_get_labels_for_span(self, store):
        store.upsert_claim(Claim(claim_id="clm-001", text="Claim 1"))
        store.upsert_claim(Claim(claim_id="clm-002", text="Claim 2"))
        store.upsert_gold_span(
            GoldSpan(span_id="span-001", document_id="doc", fixture_id="fix", char_offset=0, char_length=10, text="T")
        )

        store.upsert_claim_span_label(ClaimSpanLabel(claim_id="clm-001", span_id="span-001", relevant_to_claim=True))
        store.upsert_claim_span_label(ClaimSpanLabel(claim_id="clm-002", span_id="span-001", relevant_to_claim=False))

        labels = store.get_labels_for_span("span-001")
        assert len(labels) == 2


class TestRetrievalJudgment:
    """Test retrieval judgment operations."""

    def test_upsert_judgment(self, store):
        store.upsert_claim(Claim(claim_id="clm-001", text="Test"))

        judgment = RetrievalJudgment(
            claim_id="clm-001",
            document_id="doc-hash-123",
            forage_query_id="fq-001",
            relevant=1,
            retrieval_rank=3,
        )
        result = store.upsert_retrieval_judgment(judgment)
        assert result.created_at != ""

    def test_get_judgments_for_claim(self, store):
        store.upsert_claim(Claim(claim_id="clm-001", text="Test"))

        for i in range(3):
            store.upsert_retrieval_judgment(
                RetrievalJudgment(
                    claim_id="clm-001",
                    document_id=f"doc-{i}",
                    relevant=1 if i < 2 else 0,
                    retrieval_rank=i + 1,
                )
            )

        judgments = store.get_judgments_for_claim("clm-001")
        assert len(judgments) == 3
        # Should be ordered by rank
        assert judgments[0].retrieval_rank == 1


class TestForageStrategy:
    """Test forage strategy operations."""

    def test_upsert_strategy(self, store):
        strategy = ForageStrategyRecord(
            forage_strategy_id="fstrat-001",
            claim_id=None,
            claim_text="The Earth is old",
            mode="pregame",
            perspective="supports_claim",
            generator_version="query_generation:llm:gpt-4.1-nano",
            generator="llm",
            claim_type="factual",
            providers=["serper", "tavily"],
            source="mc5_endpoint",
            captured_at="2026-06-17T00:00:00Z",
        )
        result = store.upsert_forage_strategy(strategy)
        assert result.created_at != ""

    def test_get_strategy(self, store):
        store.upsert_forage_strategy(
            ForageStrategyRecord(
                forage_strategy_id="fstrat-001",
                claim_id=None,
                claim_text="Test",
                mode="pregame",
                perspective="supports_claim",
                generator_version="v1",
                providers=["serper"],
                source="mc5_endpoint",
                claim_decomposition={"key": "value"},
                captured_at="2026-06-17T00:00:00Z",
            )
        )

        retrieved = store.get_forage_strategy("fstrat-001")
        assert retrieved is not None
        assert retrieved.providers == ["serper"]
        assert retrieved.claim_decomposition == {"key": "value"}

    def test_get_strategies_for_claim(self, store):
        store.upsert_claim(Claim(claim_id="clm-001", text="Test"))

        for i in range(2):
            store.upsert_forage_strategy(
                ForageStrategyRecord(
                    forage_strategy_id=f"fstrat-{i}",
                    claim_id="clm-001",
                    claim_text="Test",
                    mode="pregame",
                    perspective="supports_claim" if i == 0 else "contradicts_claim",
                    generator_version="v1",
                    source="mc5_endpoint",
                    captured_at=f"2026-06-17T0{i}:00:00Z",
                )
            )

        strategies = store.get_strategies_for_claim("clm-001")
        assert len(strategies) == 2


class TestForageQuery:
    """Test forage query operations."""

    def test_upsert_query(self, store):
        # First create a strategy
        store.upsert_forage_strategy(
            ForageStrategyRecord(
                forage_strategy_id="fstrat-001",
                claim_id=None,
                claim_text="Test",
                mode="pregame",
                perspective=None,
                generator_version="v1",
                source="mc5_endpoint",
                captured_at="2026-06-17T00:00:00Z",
            )
        )

        query = ForageQueryRecord(
            forage_query_id="fq-001",
            forage_strategy_id="fstrat-001",
            pool="PRO",
            query="test query",
            strategy="direct_evidence",
            priority=0.9,
            rank=1,
            providers=["serper"],
            fixture_id="fix-001",
        )
        result = store.upsert_forage_query(query)
        assert result.created_at != ""

    def test_get_queries_for_strategy(self, store):
        store.upsert_forage_strategy(
            ForageStrategyRecord(
                forage_strategy_id="fstrat-001",
                claim_id=None,
                claim_text="Test",
                mode="pregame",
                perspective=None,
                generator_version="v1",
                source="mc5_endpoint",
                captured_at="2026-06-17T00:00:00Z",
            )
        )

        for i in range(3):
            store.upsert_forage_query(
                ForageQueryRecord(
                    forage_query_id=f"fq-{i}",
                    forage_strategy_id="fstrat-001",
                    pool="PRO" if i < 2 else "CON",
                    query=f"Query {i}",
                    rank=i + 1,
                    providers=["serper"],
                )
            )

        queries = store.get_queries_for_strategy("fstrat-001")
        assert len(queries) == 3
        # Should be ordered by rank
        assert queries[0].rank == 1


class TestDataset:
    """Test dataset metadata operations."""

    def test_get_dataset(self, store):
        dataset = store.get_dataset()
        assert dataset.schema_version == SCHEMA_VERSION
        assert dataset.dataset_version == "v1.0"

    def test_update_dataset(self, store):
        store.update_dataset(
            dataset_version="v2.0",
            annotation_guidelines_version="guidelines-v1",
        )

        dataset = store.get_dataset()
        assert dataset.dataset_version == "v2.0"
        assert dataset.annotation_guidelines_version == "guidelines-v1"


class TestCountRecords:
    """Test record counting."""

    def test_count_records(self, store):
        # Add some records
        store.upsert_claim(Claim(claim_id="clm-001", text="Test"))
        store.upsert_gold_span(
            GoldSpan(span_id="span-001", document_id="doc", fixture_id="fix", char_offset=0, char_length=10, text="T")
        )

        counts = store.count_records()
        assert counts["claim"] == 1
        assert counts["gold_span"] == 1
        assert counts["claim_span_label"] == 0
