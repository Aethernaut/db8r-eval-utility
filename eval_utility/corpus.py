"""EU-6 — Pre-RL stress claim corpus (72 claims).

This module defines the 72-claim corpus from db8r-mcts/docs/plans/2026-05-20-pre-rl-stress-claim-corpus.md.
The corpus consists of:
- 60 primary-family claims (10 per family: policy, factual, comparative, predictive, causal, existence)
- 12 hybrid claims (multi-family claims testing cross-domain interactions)

Each family has:
- 8 independent base claims + 2 reversed-polarity versions
- Evidence density distribution: 4 well, 3 mixed, 3 sparse
- Expected tendency distribution: 4 proponent, 4 respondent, 2 close

Split distribution (mirrors family balance):
- train: 70% (7 per primary family, 8 hybrids)
- dev: 15% (1-2 per primary family, 2 hybrids)
- test: 15% (1-2 per primary family, 2 hybrids) — frozen holdout, never used for tuning
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .store import Claim, GoldStore


@dataclass
class CorpusClaim:
    """A claim from the pre-RL stress corpus."""

    id: str
    family: Literal["policy", "factual", "comparative", "predictive", "causal", "existence"]
    claim: str
    evidence_density: Literal["well", "mixed", "sparse"]
    expected_tendency: Literal["proponent", "respondent", "close"]
    reverse_of: str | None = None
    notes: str | None = None
    # For hybrid claims
    primary_family: str | None = None
    secondary_families: list[str] | None = None
    expected_hybrid_behavior: str | None = None


# --- Policy Claims ---

POLICY_CLAIMS = [
    CorpusClaim(
        id="POL-01",
        family="policy",
        claim="The United States should require large employers to provide paid family leave.",
        evidence_density="well",
        expected_tendency="proponent",
        notes="Common policy evidence and comparative institutional material.",
    ),
    CorpusClaim(
        id="POL-02",
        family="policy",
        claim="The United States should ban all new natural gas hookups in residential buildings nationwide by 2028.",
        evidence_density="well",
        expected_tendency="close",
        notes="Tests benefits of electrification against overbreadth, feasibility, and exception pressure.",
    ),
    CorpusClaim(
        id="POL-03",
        family="policy",
        claim="Public schools should prohibit smartphone use during instructional time.",
        evidence_density="well",
        expected_tendency="proponent",
        notes="Tests education-outcome evidence and implementation objections.",
    ),
    CorpusClaim(
        id="POL-04",
        family="policy",
        claim="The United States should abolish all highway speed limits on interstate highways.",
        evidence_density="well",
        expected_tendency="respondent",
        notes="Strong safety evidence should support respondent pressure; proponent wins are semantic-drift sentinels.",
    ),
    CorpusClaim(
        id="POL-05",
        family="policy",
        claim="Cities should replace minimum parking requirements with market-priced parking.",
        evidence_density="mixed",
        expected_tendency="close",
        notes="Tests mixed urban-policy evidence and local-context sensitivity.",
    ),
    CorpusClaim(
        id="POL-06",
        family="policy",
        claim="Public agencies should disclose algorithmic decision systems used for benefits or enforcement.",
        evidence_density="mixed",
        expected_tendency="proponent",
        notes="Tests transparency rights, administrative feasibility, privacy exceptions, and bridge-heavy policy context.",
    ),
    CorpusClaim(
        id="POL-07",
        family="policy",
        claim="The federal government should make voting in federal elections mandatory.",
        evidence_density="mixed",
        expected_tendency="close",
        notes="Tests civic-benefit evidence against liberty and enforcement objections.",
    ),
    CorpusClaim(
        id="POL-08",
        family="policy",
        claim="Mid-sized U.S. cities should subsidize nighttime microtransit instead of fixed-route bus expansion.",
        evidence_density="sparse",
        expected_tendency="close",
        notes="Evidence likely varies by locality and transit design.",
    ),
    CorpusClaim(
        id="POL-09",
        family="policy",
        claim="The United States should not require large employers to provide paid family leave.",
        evidence_density="sparse",
        expected_tendency="close",
        reverse_of="POL-01",
        notes="Reversed-polarity partner; sparse retrieval can surface employer-cost support.",
    ),
    CorpusClaim(
        id="POL-10",
        family="policy",
        claim="The United States should not ban all new natural gas hookups in residential buildings nationwide by 2028.",
        evidence_density="sparse",
        expected_tendency="close",
        reverse_of="POL-02",
        notes="Reversed-polarity partner; unresolved benefit objections should remain visible.",
    ),
]

# --- Factual Claims ---

FACTUAL_CLAIMS = [
    CorpusClaim(
        id="FAC-01",
        family="factual",
        claim="The James Webb Space Telescope observes primarily in infrared wavelengths.",
        evidence_density="well",
        expected_tendency="proponent",
        notes="Direct factual lookup with high-quality sources.",
    ),
    CorpusClaim(
        id="FAC-02",
        family="factual",
        claim="The Panama Canal opened before the Suez Canal.",
        evidence_density="well",
        expected_tendency="respondent",
        notes="False chronology with strong documentary evidence.",
    ),
    CorpusClaim(
        id="FAC-03",
        family="factual",
        claim="Mount Kilimanjaro is located in Tanzania.",
        evidence_density="well",
        expected_tendency="proponent",
        notes="Straightforward geographic fact.",
    ),
    CorpusClaim(
        id="FAC-04",
        family="factual",
        claim="Lithium is the heaviest alkali metal.",
        evidence_density="well",
        expected_tendency="respondent",
        notes="False scientific classification detail.",
    ),
    CorpusClaim(
        id="FAC-05",
        family="factual",
        claim="Reykjavik is at roughly the same latitude as Nuuk.",
        evidence_density="mixed",
        expected_tendency="close",
        notes="Tests tolerance for approximate factual comparison.",
    ),
    CorpusClaim(
        id="FAC-06",
        family="factual",
        claim="The International Space Station orbits Earth below 1,000 kilometers.",
        evidence_density="mixed",
        expected_tendency="proponent",
        notes="Generally true but phrased with a broad threshold.",
    ),
    CorpusClaim(
        id="FAC-07",
        family="factual",
        claim="The Great Barrier Reef lies in the Atlantic Ocean.",
        evidence_density="mixed",
        expected_tendency="respondent",
        notes="False location claim with abundant corrective evidence.",
    ),
    CorpusClaim(
        id="FAC-08",
        family="factual",
        claim="The first programmable electronic computer was built in the United States.",
        evidence_density="sparse",
        expected_tendency="close",
        notes="Historically contested depending on definitions.",
    ),
    CorpusClaim(
        id="FAC-09",
        family="factual",
        claim="The James Webb Space Telescope does not observe primarily in infrared wavelengths.",
        evidence_density="sparse",
        expected_tendency="respondent",
        reverse_of="FAC-01",
        notes="Reversed-polarity partner for a strong factual claim.",
    ),
    CorpusClaim(
        id="FAC-10",
        family="factual",
        claim="The Suez Canal opened before the Panama Canal.",
        evidence_density="sparse",
        expected_tendency="proponent",
        reverse_of="FAC-02",
        notes="Reversed-polarity partner for a false chronology claim.",
    ),
]

# --- Comparative Claims ---

COMPARATIVE_CLAIMS = [
    CorpusClaim(
        id="CMP-01",
        family="comparative",
        claim="India has a larger population than Indonesia.",
        evidence_density="well",
        expected_tendency="proponent",
        notes="Direct quantitative comparison with current-source sensitivity.",
    ),
    CorpusClaim(
        id="CMP-02",
        family="comparative",
        claim="Australia has a larger land area than Canada.",
        evidence_density="well",
        expected_tendency="respondent",
        notes="False comparison with stable sources.",
    ),
    CorpusClaim(
        id="CMP-03",
        family="comparative",
        claim="The Pacific Ocean is larger than the Atlantic Ocean.",
        evidence_density="well",
        expected_tendency="proponent",
        notes="Strongly evidenced physical comparison.",
    ),
    CorpusClaim(
        id="CMP-04",
        family="comparative",
        claim="Gold is less dense than copper.",
        evidence_density="well",
        expected_tendency="respondent",
        notes="False physical-property comparison.",
    ),
    CorpusClaim(
        id="CMP-05",
        family="comparative",
        claim="The Nile River is longer than the Amazon River.",
        evidence_density="mixed",
        expected_tendency="close",
        notes="Tests contested measurement and definition handling.",
    ),
    CorpusClaim(
        id="CMP-06",
        family="comparative",
        claim="Solar power has lower operating emissions than coal power.",
        evidence_density="mixed",
        expected_tendency="proponent",
        notes="Tests lifecycle versus operating-emissions distinctions.",
    ),
    CorpusClaim(
        id="CMP-07",
        family="comparative",
        claim="The Boeing 737 MAX has a longer typical range than the Boeing 787.",
        evidence_density="mixed",
        expected_tendency="respondent",
        notes="Tests model-family specificity and quantitative comparison.",
    ),
    CorpusClaim(
        id="CMP-08",
        family="comparative",
        claim="Bus rapid transit moves more passengers per lane than light rail in most mid-sized cities.",
        evidence_density="sparse",
        expected_tendency="close",
        notes="Tests sparse, context-sensitive modal-capacity evidence.",
    ),
    CorpusClaim(
        id="CMP-09",
        family="comparative",
        claim="Indonesia has a larger population than India.",
        evidence_density="sparse",
        expected_tendency="respondent",
        reverse_of="CMP-01",
        notes="Reversed-polarity partner for a strong comparison.",
    ),
    CorpusClaim(
        id="CMP-10",
        family="comparative",
        claim="Canada has a larger land area than Australia.",
        evidence_density="sparse",
        expected_tendency="proponent",
        reverse_of="CMP-02",
        notes="Reversed-polarity partner for a false comparison.",
    ),
]

# --- Predictive Claims ---

PREDICTIVE_CLAIMS = [
    CorpusClaim(
        id="PRD-01",
        family="predictive",
        claim="NASA will return astronauts to the lunar surface before 2030.",
        evidence_density="well",
        expected_tendency="proponent",
        notes="Forecast with substantial public program evidence.",
    ),
    CorpusClaim(
        id="PRD-02",
        family="predictive",
        claim="Commercially available fully autonomous Level 5 passenger cars will be common in U.S. cities before 2028.",
        evidence_density="well",
        expected_tendency="respondent",
        notes="Tests hype-resistant future-technology forecasting.",
    ),
    CorpusClaim(
        id="PRD-03",
        family="predictive",
        claim="Global annual solar generation will increase each year through 2028.",
        evidence_density="well",
        expected_tendency="proponent",
        notes="Tests energy trend extrapolation and disruption objections.",
    ),
    CorpusClaim(
        id="PRD-04",
        family="predictive",
        claim="A crewed mission to Mars will land before 2030.",
        evidence_density="well",
        expected_tendency="respondent",
        notes="Strong timeline skepticism expected.",
    ),
    CorpusClaim(
        id="PRD-05",
        family="predictive",
        claim="India will launch a crewed Gaganyaan orbital mission before 2028.",
        evidence_density="mixed",
        expected_tendency="close",
        notes="Tests program-slippage evidence and schedule uncertainty.",
    ),
    CorpusClaim(
        id="PRD-06",
        family="predictive",
        claim="At least one major automaker will sell sodium-ion battery EVs before 2030.",
        evidence_density="mixed",
        expected_tendency="proponent",
        notes="Tests commercialization and definition of major automaker.",
    ),
    CorpusClaim(
        id="PRD-07",
        family="predictive",
        claim="A privately operated space station will fully replace the ISS before 2030.",
        evidence_density="mixed",
        expected_tendency="respondent",
        notes="Tests capability, schedule, and replacement-threshold semantics.",
    ),
    CorpusClaim(
        id="PRD-08",
        family="predictive",
        claim="A national central bank digital currency for retail public use will launch in the United States before 2030.",
        evidence_density="sparse",
        expected_tendency="close",
        notes="Tests policy forecasting under uncertain institutional signals.",
    ),
    CorpusClaim(
        id="PRD-09",
        family="predictive",
        claim="NASA will not return astronauts to the lunar surface before 2030.",
        evidence_density="sparse",
        expected_tendency="respondent",
        reverse_of="PRD-01",
        notes="Reversed-polarity partner for a proponent-favorable forecast.",
    ),
    CorpusClaim(
        id="PRD-10",
        family="predictive",
        claim="Commercially available fully autonomous Level 5 passenger cars will not be common in U.S. cities before 2028.",
        evidence_density="sparse",
        expected_tendency="proponent",
        reverse_of="PRD-02",
        notes="Reversed-polarity partner for an overoptimistic forecast.",
    ),
]

# --- Causal Claims ---

CAUSAL_CLAIMS = [
    CorpusClaim(
        id="CAU-01",
        family="causal",
        claim="Long-term exposure to fine particulate air pollution increases cardiovascular disease risk.",
        evidence_density="well",
        expected_tendency="proponent",
        notes="Strong epidemiological and mechanistic evidence.",
    ),
    CorpusClaim(
        id="CAU-02",
        family="causal",
        claim="Homeopathy causes clinically meaningful recovery from bacterial pneumonia.",
        evidence_density="well",
        expected_tendency="respondent",
        notes="Tests evidence-quality and mechanism objections.",
    ),
    CorpusClaim(
        id="CAU-03",
        family="causal",
        claim="Childhood lead exposure reduces average cognitive outcomes.",
        evidence_density="well",
        expected_tendency="proponent",
        notes="Strong causal evidence with public-health relevance.",
    ),
    CorpusClaim(
        id="CAU-04",
        family="causal",
        claim="Vaccines cause autism.",
        evidence_density="well",
        expected_tendency="respondent",
        notes="False causal claim with abundant rebuttal evidence.",
    ),
    CorpusClaim(
        id="CAU-05",
        family="causal",
        claim="Raising minimum wages consistently reduces total employment in low-wage sectors.",
        evidence_density="mixed",
        expected_tendency="close",
        notes="Tests heterogeneous causal economics evidence.",
    ),
    CorpusClaim(
        id="CAU-06",
        family="causal",
        claim="Seat belt laws reduce traffic fatalities.",
        evidence_density="mixed",
        expected_tendency="proponent",
        notes="Tests causal policy evidence and confound objections.",
    ),
    CorpusClaim(
        id="CAU-07",
        family="causal",
        claim="Eating breakfast causes sustained weight loss in adults independent of total calories.",
        evidence_density="mixed",
        expected_tendency="respondent",
        notes="Tests correlation-versus-causation handling.",
    ),
    CorpusClaim(
        id="CAU-08",
        family="causal",
        claim="Urban tree canopy expansion measurably reduces neighborhood violent crime.",
        evidence_density="sparse",
        expected_tendency="close",
        notes="Tests plausible but confounded urban causal evidence.",
    ),
    CorpusClaim(
        id="CAU-09",
        family="causal",
        claim="Long-term exposure to fine particulate air pollution does not increase cardiovascular disease risk.",
        evidence_density="sparse",
        expected_tendency="respondent",
        reverse_of="CAU-01",
        notes="Reversed-polarity partner for a strong causal claim.",
    ),
    CorpusClaim(
        id="CAU-10",
        family="causal",
        claim="Homeopathy does not cause clinically meaningful recovery from bacterial pneumonia.",
        evidence_density="sparse",
        expected_tendency="proponent",
        reverse_of="CAU-02",
        notes="Reversed-polarity partner for a weak causal claim.",
    ),
]

# --- Existence Claims ---

EXISTENCE_CLAIMS = [
    CorpusClaim(
        id="EXI-01",
        family="existence",
        claim="Methane exists in Titan's atmosphere.",
        evidence_density="well",
        expected_tendency="proponent",
        notes="Strong planetary-science evidence.",
    ),
    CorpusClaim(
        id="EXI-02",
        family="existence",
        claim="Naturally occurring liquid water currently exists on the surface of Mars.",
        evidence_density="well",
        expected_tendency="respondent",
        notes="Tests present-surface existence and transient-condition objections.",
    ),
    CorpusClaim(
        id="EXI-03",
        family="existence",
        claim="Hydrothermal vents exist on Earth's ocean floor.",
        evidence_density="well",
        expected_tendency="proponent",
        notes="Direct existence claim with strong evidence.",
    ),
    CorpusClaim(
        id="EXI-04",
        family="existence",
        claim="A stable island made primarily of plastic waste exists in the Pacific Ocean.",
        evidence_density="well",
        expected_tendency="respondent",
        notes="Tests misconception correction and aggregation semantics.",
    ),
    CorpusClaim(
        id="EXI-05",
        family="existence",
        claim="Liquid water exists beneath parts of the south polar ice cap of Mars.",
        evidence_density="mixed",
        expected_tendency="close",
        notes="Tests contested radar interpretation and uncertainty.",
    ),
    CorpusClaim(
        id="EXI-06",
        family="existence",
        claim="Water ice exists in permanently shadowed regions near the Moon's poles.",
        evidence_density="mixed",
        expected_tendency="proponent",
        notes="Tests indirect and direct measurement synthesis.",
    ),
    CorpusClaim(
        id="EXI-07",
        family="existence",
        claim="A confirmed ninth planet larger than Earth exists in the outer Solar System.",
        evidence_density="mixed",
        expected_tendency="respondent",
        notes="Tests distinction between hypothesis and confirmed existence.",
    ),
    CorpusClaim(
        id="EXI-08",
        family="existence",
        claim="Viable microbial ecosystems exist beneath the Antarctic ice sheet.",
        evidence_density="sparse",
        expected_tendency="close",
        notes="Tests difficult subsurface biosphere evidence.",
    ),
    CorpusClaim(
        id="EXI-09",
        family="existence",
        claim="Methane does not exist in Titan's atmosphere.",
        evidence_density="sparse",
        expected_tendency="respondent",
        reverse_of="EXI-01",
        notes="Reversed-polarity partner for a strong existence claim.",
    ),
    CorpusClaim(
        id="EXI-10",
        family="existence",
        claim="Naturally occurring liquid water does not currently exist on the surface of Mars.",
        evidence_density="sparse",
        expected_tendency="proponent",
        reverse_of="EXI-02",
        notes="Reversed-polarity partner for a likely false existence claim.",
    ),
]

# --- Hybrid Claims ---

HYBRID_CLAIMS = [
    CorpusClaim(
        id="HYB-01",
        family="policy",
        claim="Cities should expand congestion pricing because it reduces traffic delays.",
        evidence_density="well",
        expected_tendency="proponent",
        primary_family="policy",
        secondary_families=["causal"],
        expected_hybrid_behavior="Policy root with causal benefit material.",
    ),
    CorpusClaim(
        id="HYB-02",
        family="policy",
        claim="Cities should ban bicycle lanes because they increase traffic congestion.",
        evidence_density="well",
        expected_tendency="respondent",
        primary_family="policy",
        secondary_families=["causal"],
        expected_hybrid_behavior="Policy root with causal premise vulnerable to rebuttal.",
    ),
    CorpusClaim(
        id="HYB-03",
        family="policy",
        claim="The United States should subsidize grid-scale batteries because they will reduce blackout risk by 2035.",
        evidence_density="mixed",
        expected_tendency="close",
        primary_family="policy",
        secondary_families=["predictive"],
        expected_hybrid_behavior="Policy root with predictive capability and impact subclaims.",
    ),
    CorpusClaim(
        id="HYB-04",
        family="policy",
        claim="Public buses should receive lane priority because they move more passengers per lane than private cars.",
        evidence_density="mixed",
        expected_tendency="proponent",
        primary_family="policy",
        secondary_families=["comparative"],
        expected_hybrid_behavior="Policy root depending on comparative transportation material.",
    ),
    CorpusClaim(
        id="HYB-05",
        family="predictive",
        claim="Commercially viable fusion power plants will exist before 2035.",
        evidence_density="sparse",
        expected_tendency="respondent",
        primary_family="predictive",
        secondary_families=["existence"],
        expected_hybrid_behavior="Predictive root with existence-state diagnostics.",
    ),
    CorpusClaim(
        id="HYB-06",
        family="causal",
        claim="PFAS contamination in drinking water increases cancer risk.",
        evidence_density="well",
        expected_tendency="proponent",
        primary_family="causal",
        secondary_families=["factual"],
        expected_hybrid_behavior="Causal root requiring factual contamination and exposure material.",
    ),
    CorpusClaim(
        id="HYB-07",
        family="comparative",
        claim="India will add more solar capacity than the United States by 2030.",
        evidence_density="mixed",
        expected_tendency="close",
        primary_family="comparative",
        secondary_families=["predictive"],
        expected_hybrid_behavior="Comparative root with future-event components.",
    ),
    CorpusClaim(
        id="HYB-08",
        family="policy",
        claim="Governments should fund routine public-health screening for extraterrestrial microbial contamination because such contamination already exists on Earth.",
        evidence_density="sparse",
        expected_tendency="respondent",
        primary_family="policy",
        secondary_families=["existence"],
        expected_hybrid_behavior="Policy root with weak existence premise.",
    ),
    CorpusClaim(
        id="HYB-09",
        family="policy",
        claim="Public agencies should harden water systems because cyberattacks against water utilities have occurred.",
        evidence_density="mixed",
        expected_tendency="proponent",
        primary_family="policy",
        secondary_families=["factual"],
        expected_hybrid_behavior="Policy root with factual incident material.",
    ),
    CorpusClaim(
        id="HYB-10",
        family="causal",
        claim="Remote work reduces productivity more than it reduces commuting emissions.",
        evidence_density="mixed",
        expected_tendency="respondent",
        primary_family="causal",
        secondary_families=["comparative"],
        expected_hybrid_behavior="Causal/comparative tradeoff with likely definitional pressure.",
    ),
    CorpusClaim(
        id="HYB-11",
        family="predictive",
        claim="Widespread AI tutoring will improve national math scores before 2030.",
        evidence_density="sparse",
        expected_tendency="close",
        primary_family="predictive",
        secondary_families=["causal"],
        expected_hybrid_behavior="Predictive root with causal learning-effect material.",
    ),
    CorpusClaim(
        id="HYB-12",
        family="existence",
        claim="Microplastics exist in human blood samples and may contribute to inflammation.",
        evidence_density="mixed",
        expected_tendency="close",
        primary_family="existence",
        secondary_families=["causal"],
        expected_hybrid_behavior="Existence root with causal health-effect diagnostics.",
    ),
]

# --- All claims ---

ALL_PRIMARY_CLAIMS = (
    POLICY_CLAIMS
    + FACTUAL_CLAIMS
    + COMPARATIVE_CLAIMS
    + PREDICTIVE_CLAIMS
    + CAUSAL_CLAIMS
    + EXISTENCE_CLAIMS
)

ALL_CLAIMS = ALL_PRIMARY_CLAIMS + HYBRID_CLAIMS

# --- Split assignment ---

# Per design doc §4.9: reserve a frozen test split that mirrors family balance
# Split distribution per family (10 claims): 7 train, 2 dev, 1 test
# Hybrid (12 claims): 8 train, 2 dev, 2 test

# Assign splits by index within each family to maintain consistency
SPLIT_ASSIGNMENT = {
    # Primary families: indices 0-6 train, 7-8 dev, 9 test
    "POL-01": "train",
    "POL-02": "train",
    "POL-03": "train",
    "POL-04": "train",
    "POL-05": "train",
    "POL-06": "train",
    "POL-07": "train",
    "POL-08": "dev",
    "POL-09": "dev",
    "POL-10": "test",
    "FAC-01": "train",
    "FAC-02": "train",
    "FAC-03": "train",
    "FAC-04": "train",
    "FAC-05": "train",
    "FAC-06": "train",
    "FAC-07": "train",
    "FAC-08": "dev",
    "FAC-09": "dev",
    "FAC-10": "test",
    "CMP-01": "train",
    "CMP-02": "train",
    "CMP-03": "train",
    "CMP-04": "train",
    "CMP-05": "train",
    "CMP-06": "train",
    "CMP-07": "train",
    "CMP-08": "dev",
    "CMP-09": "dev",
    "CMP-10": "test",
    "PRD-01": "train",
    "PRD-02": "train",
    "PRD-03": "train",
    "PRD-04": "train",
    "PRD-05": "train",
    "PRD-06": "train",
    "PRD-07": "train",
    "PRD-08": "dev",
    "PRD-09": "dev",
    "PRD-10": "test",
    "CAU-01": "train",
    "CAU-02": "train",
    "CAU-03": "train",
    "CAU-04": "train",
    "CAU-05": "train",
    "CAU-06": "train",
    "CAU-07": "train",
    "CAU-08": "dev",
    "CAU-09": "dev",
    "CAU-10": "test",
    "EXI-01": "train",
    "EXI-02": "train",
    "EXI-03": "train",
    "EXI-04": "train",
    "EXI-05": "train",
    "EXI-06": "train",
    "EXI-07": "train",
    "EXI-08": "dev",
    "EXI-09": "dev",
    "EXI-10": "test",
    # Hybrids: 0-7 train, 8-9 dev, 10-11 test
    "HYB-01": "train",
    "HYB-02": "train",
    "HYB-03": "train",
    "HYB-04": "train",
    "HYB-05": "train",
    "HYB-06": "train",
    "HYB-07": "train",
    "HYB-08": "train",
    "HYB-09": "dev",
    "HYB-10": "dev",
    "HYB-11": "test",
    "HYB-12": "test",
}


def get_split(claim_id: str) -> str:
    """Get the split assignment for a claim."""
    return SPLIT_ASSIGNMENT.get(claim_id, "train")


def corpus_claim_to_store_claim(corpus_claim: CorpusClaim) -> Claim:
    """Convert a CorpusClaim to a store Claim."""
    # Build notes from corpus metadata
    notes_parts = []
    if corpus_claim.evidence_density:
        notes_parts.append(f"evidence_density={corpus_claim.evidence_density}")
    if corpus_claim.expected_tendency:
        notes_parts.append(f"expected_tendency={corpus_claim.expected_tendency}")
    if corpus_claim.reverse_of:
        notes_parts.append(f"reverse_of={corpus_claim.reverse_of}")
    if corpus_claim.primary_family:
        notes_parts.append(f"primary_family={corpus_claim.primary_family}")
    if corpus_claim.secondary_families:
        notes_parts.append(f"secondary_families={','.join(corpus_claim.secondary_families)}")
    if corpus_claim.expected_hybrid_behavior:
        notes_parts.append(f"hybrid_behavior={corpus_claim.expected_hybrid_behavior}")
    if corpus_claim.notes:
        notes_parts.append(corpus_claim.notes)

    return Claim(
        claim_id=corpus_claim.id,
        text=corpus_claim.claim,
        family=corpus_claim.family,
        split=get_split(corpus_claim.id),
        notes="; ".join(notes_parts) if notes_parts else None,
    )


def seed_corpus(store: GoldStore) -> dict[str, int]:
    """Seed the 72-claim corpus into the gold store.

    Returns:
        Dictionary with counts: {"created": N, "updated": N, "total": 72}
    """
    created = 0
    updated = 0

    for corpus_claim in ALL_CLAIMS:
        claim = corpus_claim_to_store_claim(corpus_claim)
        existing = store.get_claim(claim.claim_id)

        if existing:
            updated += 1
        else:
            created += 1

        store.upsert_claim(claim)

    return {"created": created, "updated": updated, "total": len(ALL_CLAIMS)}


def get_corpus_stats() -> dict[str, int]:
    """Get statistics about the corpus."""
    stats = {
        "total": len(ALL_CLAIMS),
        "primary": len(ALL_PRIMARY_CLAIMS),
        "hybrid": len(HYBRID_CLAIMS),
    }

    # By family
    for family in ["policy", "factual", "comparative", "predictive", "causal", "existence"]:
        stats[f"family_{family}"] = sum(1 for c in ALL_CLAIMS if c.family == family)

    # By split
    for split in ["train", "dev", "test"]:
        stats[f"split_{split}"] = sum(1 for c in ALL_CLAIMS if get_split(c.id) == split)

    # By evidence density
    for density in ["well", "mixed", "sparse"]:
        stats[f"density_{density}"] = sum(1 for c in ALL_CLAIMS if c.evidence_density == density)

    # By expected tendency
    for tendency in ["proponent", "respondent", "close"]:
        stats[f"tendency_{tendency}"] = sum(1 for c in ALL_CLAIMS if c.expected_tendency == tendency)

    return stats
