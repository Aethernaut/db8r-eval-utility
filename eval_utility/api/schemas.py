"""Pydantic schemas for the annotation API."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# --- Enums ---


class ClaimFamily(str, Enum):
    POLICY = "policy"
    FACTUAL = "factual"
    COMPARATIVE = "comparative"
    PREDICTIVE = "predictive"
    CAUSAL = "causal"
    EXISTENCE = "existence"


class ProofStandard(str, Enum):
    PE = "PE"  # Preponderance of Evidence
    CCE = "CCE"  # Clear and Convincing Evidence
    BRD = "BRD"  # Beyond Reasonable Doubt
    DV = "DV"  # Dialectical Validity


class Split(str, Enum):
    TRAIN = "train"
    DEV = "dev"
    TEST = "test"


class LinkOrigin(str, Enum):
    SEARCH = "search"
    MANUAL = "manual"


class LabelSource(str, Enum):
    PIPELINE_PREFILL = "pipeline_prefill"
    PIPELINE_PREFILL_CORRECTED = "pipeline_prefill_corrected"
    HUMAN_AUTHORED = "human_authored"


# --- Evidence Quality Enums (Foraging Learning) ---


class DocumentRelevance(str, Enum):
    """Document-level relevance to claim (T1 categorical)."""

    GERMANE = "germane"  # Directly relevant, contains usable evidence
    PARTIALLY_GERMANE = "partially_germane"  # Some relevant content
    BACKGROUND = "background"  # Provides context but not direct evidence
    IRRELEVANT = "irrelevant"  # No bearing on the claim


class ClaimRelation(str, Enum):
    """Document's relation to the target claim."""

    SUPPORTS = "supports"  # Evidence supports the claim
    CONTRADICTS = "contradicts"  # Evidence contradicts the claim
    MIXED = "mixed"  # Contains both supporting and contradicting evidence
    BACKGROUND = "background"  # Contextual, not argumentative
    UNCLEAR = "unclear"  # Relation cannot be determined


class ExtractionQuality(str, Enum):
    """Quality of extracted claim relative to source text."""

    FAITHFUL = "faithful"  # Accurately represents source
    OVERBROAD = "overbroad"  # Claims more than source supports
    UNDERSPECIFIED = "underspecified"  # Missing important qualifiers
    WRONG = "wrong"  # Misrepresents source
    UNSUPPORTED = "unsupported"  # No source basis for claim


class GroundingQuality(str, Enum):
    """Quality of span grounding in source document."""

    SUFFICIENT = "sufficient"  # Span + context adequate
    MISSING_CONTEXT = "missing_context"  # Need more surrounding text
    WRONG_SPAN = "wrong_span"  # Span boundaries incorrect
    SOURCE_MISMATCH = "source_mismatch"  # Span doesn't match source doc


class EvidenceUsability(str, Enum):
    """Usability of evidence in debate context."""

    ARGUMENT_SUPPORT = "argument_support"  # Could support main argument
    REBUTTAL_SUPPORT = "rebuttal_support"  # Could support rebuttal
    CONTEXT_ONLY = "context_only"  # Background, not argumentative
    UNUSABLE = "unusable"  # Cannot use in debate


class CorroborationStatus(str, Enum):
    """Whether evidence is independent or duplicated."""

    INDEPENDENT = "independent"  # Genuinely independent source
    SAME_CLUSTER = "same_cluster"  # Same underlying source/wire story
    DUPLICATE = "duplicate"  # Exact or near duplicate


class SourceIssue(str, Enum):
    """Issues with source document quality/accessibility."""

    NONE = "none"
    PAYWALL_PARTIAL = "paywall_partial"  # Partial extraction due to paywall
    WEAK_ATTRIBUTION = "weak_attribution"  # Source attribution unclear
    STALE_SOURCE = "stale_source"  # Information may be outdated
    LOW_QUALITY_SOURCE = "low_quality_source"  # Unreliable source
    MISSING_PRIMARY = "missing_primary"  # References primary not included


class Stance(str, Enum):
    PRO = "PRO"
    CON = "CON"
    NEUTRAL = "NEUTRAL"


class StrengthOrdinal(str, Enum):
    NONE = "none"
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"


class Pool(str, Enum):
    PRO = "PRO"
    CON = "CON"


class ForageMode(str, Enum):
    PREGAME = "pregame"
    REACTIVE = "reactive"


class Perspective(str, Enum):
    SUPPORTS_CLAIM = "supports_claim"
    CONTRADICTS_CLAIM = "contradicts_claim"


class ForageSource(str, Enum):
    MC5_ENDPOINT = "mc5_endpoint"
    DEBATE_TRACE = "debate_trace"


# --- Claim Schemas ---


class ClaimCreate(BaseModel):
    text: str
    family: ClaimFamily | None = None
    proof_standard: ProofStandard | None = None
    split: Split = Split.TRAIN
    notes: str | None = None


class ClaimUpdate(BaseModel):
    text: str | None = None
    family: ClaimFamily | None = None
    proof_standard: ProofStandard | None = None
    split: Split | None = None
    notes: str | None = None
    retrieval_complete: bool | None = None


class ClaimResponse(BaseModel):
    claim_id: str
    text: str
    family: ClaimFamily | None = None
    proof_standard: ProofStandard | None = None
    split: Split
    notes: str | None = None
    retrieval_complete: bool = False
    created_at: str
    updated_at: str


class ClaimListResponse(BaseModel):
    claims: list[ClaimResponse]
    total: int


# --- Claim-Document Link Schemas ---


class ClaimDocumentLinkCreate(BaseModel):
    document_id: str
    origin: LinkOrigin = LinkOrigin.MANUAL
    fixture_id: str | None = None
    notes: str | None = None


class ClaimDocumentLinkResponse(BaseModel):
    claim_id: str
    document_id: str
    origin: LinkOrigin
    fixture_id: str | None = None
    notes: str | None = None
    created_at: str


# --- Document Annotation Schemas ---


class DocumentAnnotationUpdate(BaseModel):
    exhaustively_annotated: bool | None = None
    lost_evidence_flag: bool | None = None
    lost_evidence_note: str | None = None
    annotator_id: str | None = None


class DocumentAnnotationResponse(BaseModel):
    document_id: str
    fixture_id: str
    exhaustively_annotated: bool
    lost_evidence_flag: bool
    lost_evidence_note: str | None = None
    annotator_id: str | None = None
    created_at: str
    updated_at: str
    # CC-3: MBFC Source Reliability metadata
    publisher_name: str | None = None
    publisher_mbfc_key: str | None = None
    mbfc_factual_rating: str | None = None
    mbfc_bias_rating: str | None = None
    source_reliability: float | None = None


# --- Gold Span Schemas ---


class GoldSpanCreate(BaseModel):
    document_id: str
    fixture_id: str
    char_offset: int = Field(..., ge=0)
    char_length: int = Field(..., gt=0)
    text: str
    is_claim_bearing: bool | None = None
    label_source: LabelSource | None = None
    annotator_id: str | None = None
    notes: str | None = None


class GoldSpanUpdate(BaseModel):
    is_claim_bearing: bool | None = None
    label_source: LabelSource | None = None
    annotator_id: str | None = None
    notes: str | None = None


class GoldSpanResponse(BaseModel):
    span_id: str
    document_id: str
    fixture_id: str
    char_offset: int
    char_length: int
    text: str
    is_claim_bearing: bool | None = None
    label_source: LabelSource | None = None
    annotator_id: str | None = None
    notes: str | None = None
    created_at: str
    updated_at: str
    # CC-3: Claim Attribution metadata
    claim_attribution: dict[str, Any] | None = None
    claimant_name: str | None = None
    claimant_key: str | None = None
    attribution_type: str | None = None


class GoldSpanListResponse(BaseModel):
    spans: list[GoldSpanResponse]
    total: int


class SpanPrefillRequest(BaseModel):
    fixture_id: str
    document_id: str  # source_text_hash
    label_source: LabelSource = LabelSource.PIPELINE_PREFILL
    overwrite_existing: bool = False


class SpanPrefillResponse(BaseModel):
    created_count: int
    skipped_count: int
    spans: list[GoldSpanResponse]


# --- Claim-Span Label Schemas ---


class ClaimSpanLabelCreate(BaseModel):
    claim_id: str
    span_id: str
    relevant_to_claim: bool | None = None
    stance: Stance | None = None
    strength_ordinal: StrengthOrdinal | None = None
    annotator_id: str | None = None
    notes: str | None = None


class ClaimSpanLabelUpdate(BaseModel):
    relevant_to_claim: bool | None = None
    stance: Stance | None = None
    strength_ordinal: StrengthOrdinal | None = None
    annotator_id: str | None = None
    notes: str | None = None


class ClaimSpanLabelResponse(BaseModel):
    claim_id: str
    span_id: str
    relevant_to_claim: bool | None = None
    stance: Stance | None = None
    strength_ordinal: StrengthOrdinal | None = None
    annotator_id: str | None = None
    notes: str | None = None
    created_at: str
    updated_at: str


class ClaimSpanLabelListResponse(BaseModel):
    labels: list[ClaimSpanLabelResponse]
    total: int


class LabelBatchRequest(BaseModel):
    labels: list[ClaimSpanLabelCreate]


class LabelBatchResponse(BaseModel):
    created_count: int
    updated_count: int
    labels: list[ClaimSpanLabelResponse]


# --- Retrieval Judgment Schemas ---


class RetrievalJudgmentCreate(BaseModel):
    claim_id: str
    document_id: str
    forage_query_id: str | None = None
    relevant: int | None = None  # bool or graded 0-3
    retrieval_rank: int | None = None
    annotator_id: str | None = None
    notes: str | None = None


class RetrievalJudgmentUpdate(BaseModel):
    forage_query_id: str | None = None
    relevant: int | None = None
    retrieval_rank: int | None = None
    annotator_id: str | None = None
    notes: str | None = None


class RetrievalJudgmentResponse(BaseModel):
    claim_id: str
    document_id: str
    forage_query_id: str | None = None
    relevant: int | None = None
    retrieval_rank: int | None = None
    annotator_id: str | None = None
    notes: str | None = None
    created_at: str
    updated_at: str


class RetrievalJudgmentListResponse(BaseModel):
    judgments: list[RetrievalJudgmentResponse]
    total: int


class JudgmentBatchRequest(BaseModel):
    judgments: list[RetrievalJudgmentCreate]


class JudgmentBatchResponse(BaseModel):
    created_count: int
    updated_count: int
    judgments: list[RetrievalJudgmentResponse]


# --- Evidence Quality Labels (Foraging Learning) ---


class DocumentQualityLabelCreate(BaseModel):
    """Create/update document-level quality labels."""

    document_id: str
    claim_id: str | None = None  # Optional: some labels are claim-specific
    # Core relevance (extends T1 numeric scale with categorical)
    relevance: DocumentRelevance | None = None
    claim_relation: ClaimRelation | None = None
    # Source quality issues (can have multiple)
    source_issues: list[SourceIssue] | None = None
    # Corroboration tracking
    corroboration_status: CorroborationStatus | None = None
    corroboration_cluster_id: str | None = None  # Links related docs
    # Metadata
    annotator_id: str | None = None
    notes: str | None = None


class DocumentQualityLabelUpdate(BaseModel):
    """Update document-level quality labels."""

    relevance: DocumentRelevance | None = None
    claim_relation: ClaimRelation | None = None
    source_issues: list[SourceIssue] | None = None
    corroboration_status: CorroborationStatus | None = None
    corroboration_cluster_id: str | None = None
    annotator_id: str | None = None
    notes: str | None = None


class DocumentQualityLabelResponse(BaseModel):
    """Document-level quality label response."""

    id: str
    document_id: str
    claim_id: str | None = None
    relevance: DocumentRelevance | None = None
    claim_relation: ClaimRelation | None = None
    source_issues: list[SourceIssue] | None = None
    corroboration_status: CorroborationStatus | None = None
    corroboration_cluster_id: str | None = None
    annotator_id: str | None = None
    notes: str | None = None
    created_at: str
    updated_at: str


class DocumentQualityLabelListResponse(BaseModel):
    """List of document quality labels."""

    labels: list[DocumentQualityLabelResponse]
    total: int


class SpanQualityLabelCreate(BaseModel):
    """Create/update span-level quality labels."""

    span_id: str
    # Extraction quality
    extraction_quality: ExtractionQuality | None = None
    # Grounding quality
    grounding_quality: GroundingQuality | None = None
    # Evidence usability
    evidence_usability: EvidenceUsability | None = None
    # Metadata
    annotator_id: str | None = None
    notes: str | None = None


class SpanQualityLabelUpdate(BaseModel):
    """Update span-level quality labels."""

    extraction_quality: ExtractionQuality | None = None
    grounding_quality: GroundingQuality | None = None
    evidence_usability: EvidenceUsability | None = None
    annotator_id: str | None = None
    notes: str | None = None


class SpanQualityLabelResponse(BaseModel):
    """Span-level quality label response."""

    id: str
    span_id: str
    extraction_quality: ExtractionQuality | None = None
    grounding_quality: GroundingQuality | None = None
    evidence_usability: EvidenceUsability | None = None
    annotator_id: str | None = None
    notes: str | None = None
    created_at: str
    updated_at: str


class SpanQualityLabelListResponse(BaseModel):
    """List of span quality labels."""

    labels: list[SpanQualityLabelResponse]
    total: int


# --- Forage Strategy Schemas ---


class ForageQueryResponse(BaseModel):
    forage_query_id: str
    forage_strategy_id: str
    pool: Pool
    query: str
    strategy: str | None = None
    priority: float | None = None
    rank: int | None = None
    providers: list[str]
    intent_label: str | None = None
    rationale: str | None = None
    retrieval_role: str | None = None
    scheme: str | None = None
    critical_question_family: str | None = None
    target_schema_need_id: str | None = None
    fixture_id: str | None = None
    created_at: str


class ForageQueryListResponse(BaseModel):
    queries: list[ForageQueryResponse]
    total: int


class ForageStrategyResponse(BaseModel):
    forage_strategy_id: str
    claim_id: str | None = None
    claim_text: str | None = None
    mode: ForageMode
    perspective: Perspective | None = None
    generator_version: str
    generator: str | None = None
    claim_type: str | None = None
    providers: list[str]
    context: dict[str, Any] | None = None
    source: ForageSource
    fallback_reason: str | None = None
    claim_decomposition: dict[str, Any] | None = None
    polarity_reversal: dict[str, Any] | None = None
    schema_plan: dict[str, Any] | None = None
    captured_at: str
    created_at: str


class ForageStrategyDetailResponse(ForageStrategyResponse):
    queries: list[ForageQueryResponse]


class ForageStrategyListResponse(BaseModel):
    strategies: list[ForageStrategyResponse]
    total: int


# --- Fixture Schemas (read-only) ---


class ExtractionStatusResponse(BaseModel):
    partial_extraction: bool
    chunks_processed: int | None = None
    chunks_total: int | None = None
    tokens_used: int | None = None
    token_budget: int | None = None
    warnings: list[str]


class FixtureDocumentResponse(BaseModel):
    document_id: str
    source_url: str
    source_title: str | None = None
    source_domain: str | None = None
    provider: str | None = None
    content_type: str | None = None
    fetched_at: str | None = None
    source_reliability: float | None = None
    retrieval_rank: int | None = None
    source_text_hash: str
    source_text_char_len: int
    extraction_status: ExtractionStatusResponse | None = None
    validation_warnings: list[str]
    # CC-3: MBFC Source Reliability metadata
    publisher_name: str | None = None
    publisher_mbfc_key: str | None = None
    mbfc_factual_rating: str | None = None
    mbfc_bias_rating: str | None = None


class FixtureDocumentDetailResponse(FixtureDocumentResponse):
    source_text: str
    fixture_id: str | None = None  # Set when returned from /documents/next


class FixtureSpanResponse(BaseModel):
    claim_id: str
    document_id: str
    text: str
    char_offset: int
    char_length: int
    extraction_fidelity: float | None = None
    match_method: str | None = None
    source_assertion_opinion: dict[str, Any] | None = None
    claimset_orientation: str | None = None
    relevance_score: float | None = None
    verbatim_span: str | None = None
    # CC-3: Claim Attribution metadata
    claim_attribution: dict[str, Any] | None = None
    claimant_name: str | None = None
    claimant_key: str | None = None
    attribution_type: str | None = None


class FixtureRetrievalResultResponse(BaseModel):
    document_id: str | None = None
    url: str
    title: str | None = None
    rank: int
    provider: str | None = None
    relevance_score: float | None = None
    status: str | None = None
    error: str | None = None


class FixtureSummaryResponse(BaseModel):
    fixture_id: str
    capture_mode: str
    query: str | None = None
    job_id: str | None = None
    claimcheck_version: str | None = None
    captured_at: str
    schema_version: str
    document_count: int
    span_count: int
    retrieval_result_count: int
    has_partial_extraction: bool
    forage_strategy_id: str | None = None
    forage_query_id: str | None = None


class FixtureDetailResponse(BaseModel):
    fixture_id: str
    capture_mode: str
    query: str | None = None
    job_id: str | None = None
    claimcheck_version: str | None = None
    captured_at: str
    schema_version: str
    extraction_status: ExtractionStatusResponse | None = None
    forage_strategy_id: str | None = None
    forage_query_id: str | None = None
    documents: list[FixtureDocumentResponse]
    spans: list[FixtureSpanResponse]
    retrieval_results: list[FixtureRetrievalResultResponse]


class FixtureListResponse(BaseModel):
    fixtures: list[FixtureSummaryResponse]
    total: int


# --- Dataset Schemas ---


class DatasetResponse(BaseModel):
    dataset_version: str
    schema_version: str
    annotation_guidelines_version: str | None = None
    created_at: str
    updated_at: str
    record_counts: dict[str, int]


class DatasetUpdate(BaseModel):
    dataset_version: str | None = None
    annotation_guidelines_version: str | None = None


# --- Health Schema ---


class HealthResponse(BaseModel):
    status: str
    version: str
    database_connected: bool = True
