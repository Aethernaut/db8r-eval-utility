"""Tests for the corpus module."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from eval_utility.corpus import (
    ALL_CLAIMS,
    ALL_PRIMARY_CLAIMS,
    CAUSAL_CLAIMS,
    COMPARATIVE_CLAIMS,
    EXISTENCE_CLAIMS,
    FACTUAL_CLAIMS,
    HYBRID_CLAIMS,
    POLICY_CLAIMS,
    PREDICTIVE_CLAIMS,
    SPLIT_ASSIGNMENT,
    corpus_claim_to_store_claim,
    get_corpus_stats,
    get_split,
    seed_corpus,
)
from eval_utility.store import GoldStore


class TestCorpusStructure:
    """Tests for corpus structure and completeness."""

    def test_total_claims(self):
        """Verify total claim count is 72."""
        assert len(ALL_CLAIMS) == 72

    def test_primary_claims_count(self):
        """Verify 60 primary family claims."""
        assert len(ALL_PRIMARY_CLAIMS) == 60

    def test_hybrid_claims_count(self):
        """Verify 12 hybrid claims."""
        assert len(HYBRID_CLAIMS) == 12

    def test_per_family_count(self):
        """Verify 10 claims per primary family."""
        assert len(POLICY_CLAIMS) == 10
        assert len(FACTUAL_CLAIMS) == 10
        assert len(COMPARATIVE_CLAIMS) == 10
        assert len(PREDICTIVE_CLAIMS) == 10
        assert len(CAUSAL_CLAIMS) == 10
        assert len(EXISTENCE_CLAIMS) == 10

    def test_unique_claim_ids(self):
        """Verify all claim IDs are unique."""
        ids = [c.id for c in ALL_CLAIMS]
        assert len(ids) == len(set(ids))

    def test_claim_id_prefixes(self):
        """Verify claim ID prefixes match families."""
        for claim in POLICY_CLAIMS:
            assert claim.id.startswith("POL-")
        for claim in FACTUAL_CLAIMS:
            assert claim.id.startswith("FAC-")
        for claim in COMPARATIVE_CLAIMS:
            assert claim.id.startswith("CMP-")
        for claim in PREDICTIVE_CLAIMS:
            assert claim.id.startswith("PRD-")
        for claim in CAUSAL_CLAIMS:
            assert claim.id.startswith("CAU-")
        for claim in EXISTENCE_CLAIMS:
            assert claim.id.startswith("EXI-")
        for claim in HYBRID_CLAIMS:
            assert claim.id.startswith("HYB-")


class TestEvidenceDensityDistribution:
    """Tests for evidence density distribution per family."""

    def test_evidence_density_values(self):
        """Verify all claims have valid evidence density."""
        for claim in ALL_CLAIMS:
            assert claim.evidence_density in ["well", "mixed", "sparse"]

    def test_per_family_density_distribution(self):
        """Verify each primary family has 4 well, 3 mixed, 3 sparse."""
        for family_claims in [
            POLICY_CLAIMS,
            FACTUAL_CLAIMS,
            COMPARATIVE_CLAIMS,
            PREDICTIVE_CLAIMS,
            CAUSAL_CLAIMS,
            EXISTENCE_CLAIMS,
        ]:
            well = sum(1 for c in family_claims if c.evidence_density == "well")
            mixed = sum(1 for c in family_claims if c.evidence_density == "mixed")
            sparse = sum(1 for c in family_claims if c.evidence_density == "sparse")

            assert well == 4, f"Expected 4 'well' claims, got {well}"
            assert mixed == 3, f"Expected 3 'mixed' claims, got {mixed}"
            assert sparse == 3, f"Expected 3 'sparse' claims, got {sparse}"


class TestExpectedTendencyDistribution:
    """Tests for expected tendency distribution."""

    def test_expected_tendency_values(self):
        """Verify all claims have valid expected tendency."""
        for claim in ALL_CLAIMS:
            assert claim.expected_tendency in ["proponent", "respondent", "close"]


class TestReversedPolarityClaims:
    """Tests for reversed-polarity claim pairs."""

    def test_reversed_claims_count(self):
        """Verify each primary family has 2 reversed claims."""
        for family_claims in [
            POLICY_CLAIMS,
            FACTUAL_CLAIMS,
            COMPARATIVE_CLAIMS,
            PREDICTIVE_CLAIMS,
            CAUSAL_CLAIMS,
            EXISTENCE_CLAIMS,
        ]:
            reversed_count = sum(1 for c in family_claims if c.reverse_of is not None)
            assert reversed_count == 2, f"Expected 2 reversed claims, got {reversed_count}"

    def test_reversed_claims_reference_valid_ids(self):
        """Verify reverse_of references exist."""
        all_ids = {c.id for c in ALL_CLAIMS}
        for claim in ALL_CLAIMS:
            if claim.reverse_of:
                assert claim.reverse_of in all_ids, f"{claim.id} references non-existent {claim.reverse_of}"

    def test_reversed_claims_same_family(self):
        """Verify reversed claims are in the same family as their base."""
        claim_map = {c.id: c for c in ALL_CLAIMS}
        for claim in ALL_CLAIMS:
            if claim.reverse_of:
                base = claim_map[claim.reverse_of]
                assert claim.family == base.family


class TestHybridClaims:
    """Tests for hybrid claims."""

    def test_hybrid_claims_have_primary_family(self):
        """Verify all hybrid claims have primary_family set."""
        for claim in HYBRID_CLAIMS:
            assert claim.primary_family is not None

    def test_hybrid_claims_have_secondary_families(self):
        """Verify all hybrid claims have secondary_families set."""
        for claim in HYBRID_CLAIMS:
            assert claim.secondary_families is not None
            assert len(claim.secondary_families) >= 1

    def test_hybrid_claims_have_behavior(self):
        """Verify all hybrid claims have expected_hybrid_behavior."""
        for claim in HYBRID_CLAIMS:
            assert claim.expected_hybrid_behavior is not None


class TestSplitAssignment:
    """Tests for train/dev/test split assignment."""

    def test_all_claims_have_split(self):
        """Verify all claims are in SPLIT_ASSIGNMENT."""
        for claim in ALL_CLAIMS:
            assert claim.id in SPLIT_ASSIGNMENT

    def test_split_values(self):
        """Verify all splits are valid."""
        for claim_id, split in SPLIT_ASSIGNMENT.items():
            assert split in ["train", "dev", "test"]

    def test_split_distribution_primary(self):
        """Verify split distribution for primary families: 7 train, 2 dev, 1 test each."""
        for family_claims in [
            POLICY_CLAIMS,
            FACTUAL_CLAIMS,
            COMPARATIVE_CLAIMS,
            PREDICTIVE_CLAIMS,
            CAUSAL_CLAIMS,
            EXISTENCE_CLAIMS,
        ]:
            train = sum(1 for c in family_claims if get_split(c.id) == "train")
            dev = sum(1 for c in family_claims if get_split(c.id) == "dev")
            test = sum(1 for c in family_claims if get_split(c.id) == "test")

            assert train == 7, f"Expected 7 train, got {train}"
            assert dev == 2, f"Expected 2 dev, got {dev}"
            assert test == 1, f"Expected 1 test, got {test}"

    def test_split_distribution_hybrid(self):
        """Verify split distribution for hybrids: 8 train, 2 dev, 2 test."""
        train = sum(1 for c in HYBRID_CLAIMS if get_split(c.id) == "train")
        dev = sum(1 for c in HYBRID_CLAIMS if get_split(c.id) == "dev")
        test = sum(1 for c in HYBRID_CLAIMS if get_split(c.id) == "test")

        assert train == 8, f"Expected 8 train, got {train}"
        assert dev == 2, f"Expected 2 dev, got {dev}"
        assert test == 2, f"Expected 2 test, got {test}"

    def test_overall_split_distribution(self):
        """Verify overall split distribution."""
        train = sum(1 for c in ALL_CLAIMS if get_split(c.id) == "train")
        dev = sum(1 for c in ALL_CLAIMS if get_split(c.id) == "dev")
        test = sum(1 for c in ALL_CLAIMS if get_split(c.id) == "test")

        # 6 families × 7 train + 8 hybrid train = 50 train
        # 6 families × 2 dev + 2 hybrid dev = 14 dev
        # 6 families × 1 test + 2 hybrid test = 8 test
        assert train == 50, f"Expected 50 train, got {train}"
        assert dev == 14, f"Expected 14 dev, got {dev}"
        assert test == 8, f"Expected 8 test, got {test}"


class TestCorpusClaimToStoreClaim:
    """Tests for converting corpus claims to store claims."""

    def test_basic_conversion(self):
        """Test basic conversion of a corpus claim."""
        corpus_claim = POLICY_CLAIMS[0]  # POL-01
        store_claim = corpus_claim_to_store_claim(corpus_claim)

        assert store_claim.claim_id == "POL-01"
        assert store_claim.text == corpus_claim.claim
        assert store_claim.family == "policy"
        assert store_claim.split == "train"

    def test_notes_contain_metadata(self):
        """Test that notes contain relevant metadata."""
        corpus_claim = POLICY_CLAIMS[0]
        store_claim = corpus_claim_to_store_claim(corpus_claim)

        assert "evidence_density=well" in store_claim.notes
        assert "expected_tendency=proponent" in store_claim.notes

    def test_reversed_claim_notes(self):
        """Test that reversed claims have reverse_of in notes."""
        corpus_claim = POLICY_CLAIMS[8]  # POL-09, reversed
        store_claim = corpus_claim_to_store_claim(corpus_claim)

        assert "reverse_of=POL-01" in store_claim.notes

    def test_hybrid_claim_notes(self):
        """Test that hybrid claims have hybrid info in notes."""
        corpus_claim = HYBRID_CLAIMS[0]  # HYB-01
        store_claim = corpus_claim_to_store_claim(corpus_claim)

        assert "primary_family=policy" in store_claim.notes
        assert "secondary_families=causal" in store_claim.notes


class TestGetCorpusStats:
    """Tests for corpus statistics."""

    def test_stats_total(self):
        """Test total count."""
        stats = get_corpus_stats()
        assert stats["total"] == 72

    def test_stats_primary_hybrid(self):
        """Test primary and hybrid counts."""
        stats = get_corpus_stats()
        assert stats["primary"] == 60
        assert stats["hybrid"] == 12

    def test_stats_by_family(self):
        """Test counts by family."""
        stats = get_corpus_stats()
        # Count hybrid claims by family:
        # HYB-01,02,03,04,08,09 = policy (6), HYB-05,11 = predictive (2),
        # HYB-06,10 = causal (2), HYB-07 = comparative (1), HYB-12 = existence (1)
        assert stats["family_policy"] == 10 + 6  # 10 primary + 6 hybrid
        assert stats["family_factual"] == 10  # 10 primary only
        assert stats["family_comparative"] == 10 + 1  # 10 primary + 1 hybrid (HYB-07)
        assert stats["family_predictive"] == 10 + 2  # 10 primary + 2 hybrid (HYB-05,11)
        assert stats["family_causal"] == 10 + 2  # 10 primary + 2 hybrid (HYB-06,10)
        assert stats["family_existence"] == 10 + 1  # 10 primary + 1 hybrid (HYB-12)

    def test_stats_by_split(self):
        """Test counts by split."""
        stats = get_corpus_stats()
        assert stats["split_train"] == 50
        assert stats["split_dev"] == 14
        assert stats["split_test"] == 8


class TestSeedCorpus:
    """Tests for seeding the corpus into the store."""

    @pytest.fixture
    def temp_store(self):
        """Create a temporary store."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test_gold.db"
            yield GoldStore(db_path=db_path)

    def test_seed_creates_claims(self, temp_store):
        """Test that seeding creates all 72 claims."""
        result = seed_corpus(temp_store)

        assert result["total"] == 72
        assert result["created"] == 72
        assert result["updated"] == 0

    def test_seed_idempotent(self, temp_store):
        """Test that seeding is idempotent."""
        # First seed
        result1 = seed_corpus(temp_store)
        assert result1["created"] == 72

        # Second seed
        result2 = seed_corpus(temp_store)
        assert result2["created"] == 0
        assert result2["updated"] == 72

    def test_seeded_claims_retrievable(self, temp_store):
        """Test that seeded claims can be retrieved."""
        seed_corpus(temp_store)

        # Check a few claims
        pol01 = temp_store.get_claim("POL-01")
        assert pol01 is not None
        assert pol01.family == "policy"
        assert pol01.split == "train"

        hyb12 = temp_store.get_claim("HYB-12")
        assert hyb12 is not None
        assert hyb12.family == "existence"
        assert hyb12.split == "test"

    def test_seeded_claims_list_by_family(self, temp_store):
        """Test listing seeded claims by family."""
        seed_corpus(temp_store)

        policy_claims = temp_store.list_claims(family="policy")
        # 10 primary + 6 hybrid with policy as family
        assert len(policy_claims) == 16

    def test_seeded_claims_list_by_split(self, temp_store):
        """Test listing seeded claims by split."""
        seed_corpus(temp_store)

        test_claims = temp_store.list_claims(split="test")
        assert len(test_claims) == 8


class TestClaimContent:
    """Tests for claim content validity."""

    def test_claims_have_non_empty_text(self):
        """Verify all claims have non-empty text."""
        for claim in ALL_CLAIMS:
            assert claim.claim.strip(), f"Claim {claim.id} has empty text"

    def test_claims_have_family(self):
        """Verify all claims have a family."""
        for claim in ALL_CLAIMS:
            assert claim.family in [
                "policy",
                "factual",
                "comparative",
                "predictive",
                "causal",
                "existence",
            ]

    def test_claim_text_reasonable_length(self):
        """Verify claim text is reasonable length."""
        for claim in ALL_CLAIMS:
            assert len(claim.claim) > 20, f"Claim {claim.id} too short"
            assert len(claim.claim) < 500, f"Claim {claim.id} too long"
