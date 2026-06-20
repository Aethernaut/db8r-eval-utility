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


class ClaimResponse(BaseModel):
    claim_id: str
    text: str
    family: ClaimFamily | None = None
    proof_standard: ProofStandard | None = None
    split: Split
    notes: str | None = None
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


class FixtureDocumentDetailResponse(FixtureDocumentResponse):
    source_text: str


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
