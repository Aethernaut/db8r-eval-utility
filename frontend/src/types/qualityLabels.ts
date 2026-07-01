/**
 * Quality label types for foraging learning.
 * These labels assess evidence quality at document and span levels.
 */

// --- Document-level enums ---

export type DocumentRelevance = 'germane' | 'partially_germane' | 'background' | 'irrelevant';

export type ClaimRelation = 'supports' | 'contradicts' | 'mixed' | 'background' | 'unclear';

export type CorroborationStatus = 'independent' | 'same_cluster' | 'duplicate';

export type SourceIssue =
  | 'none'
  | 'paywall_partial'
  | 'weak_attribution'
  | 'stale_source'
  | 'low_quality_source'
  | 'missing_primary';

// --- Span-level enums ---

export type ExtractionQuality = 'faithful' | 'overbroad' | 'underspecified' | 'wrong' | 'unsupported';

export type GroundingQuality = 'sufficient' | 'missing_context' | 'wrong_span' | 'source_mismatch';

export type EvidenceUsability = 'argument_support' | 'rebuttal_support' | 'context_only' | 'unusable';

// --- API Response types ---

export interface DocumentQualityLabel {
  id: string;
  document_id: string;
  claim_id: string | null;
  relevance: DocumentRelevance | null;
  claim_relation: ClaimRelation | null;
  source_issues: SourceIssue[] | null;
  corroboration_status: CorroborationStatus | null;
  corroboration_cluster_id: string | null;
  annotator_id: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface SpanQualityLabel {
  id: string;
  span_id: string;
  extraction_quality: ExtractionQuality | null;
  grounding_quality: GroundingQuality | null;
  evidence_usability: EvidenceUsability | null;
  annotator_id: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

// --- Label options for UI ---

export const DOCUMENT_RELEVANCE_OPTIONS: { value: DocumentRelevance; label: string; description: string }[] = [
  { value: 'germane', label: 'Germane', description: 'Directly relevant, contains usable evidence' },
  { value: 'partially_germane', label: 'Partially Germane', description: 'Some relevant content' },
  { value: 'background', label: 'Background', description: 'Provides context but not direct evidence' },
  { value: 'irrelevant', label: 'Irrelevant', description: 'No bearing on the claim' },
];

export const CLAIM_RELATION_OPTIONS: { value: ClaimRelation; label: string; description: string }[] = [
  { value: 'supports', label: 'Supports', description: 'Evidence supports the claim' },
  { value: 'contradicts', label: 'Contradicts', description: 'Evidence contradicts the claim' },
  { value: 'mixed', label: 'Mixed', description: 'Contains both supporting and contradicting evidence' },
  { value: 'background', label: 'Background', description: 'Contextual, not argumentative' },
  { value: 'unclear', label: 'Unclear', description: 'Relation cannot be determined' },
];

export const SOURCE_ISSUE_OPTIONS: { value: SourceIssue; label: string; description: string }[] = [
  { value: 'none', label: 'None', description: 'No issues with source' },
  { value: 'paywall_partial', label: 'Paywall/Partial', description: 'Partial extraction due to paywall' },
  { value: 'weak_attribution', label: 'Weak Attribution', description: 'Source attribution unclear' },
  { value: 'stale_source', label: 'Stale Source', description: 'Information may be outdated' },
  { value: 'low_quality_source', label: 'Low Quality', description: 'Unreliable source' },
  { value: 'missing_primary', label: 'Missing Primary', description: 'References primary source not included' },
];

export const CORROBORATION_OPTIONS: { value: CorroborationStatus; label: string; description: string }[] = [
  { value: 'independent', label: 'Independent', description: 'Genuinely independent source' },
  { value: 'same_cluster', label: 'Same Cluster', description: 'Same underlying source/wire story' },
  { value: 'duplicate', label: 'Duplicate', description: 'Exact or near duplicate' },
];

export const EXTRACTION_QUALITY_OPTIONS: { value: ExtractionQuality; label: string; description: string }[] = [
  { value: 'faithful', label: 'Faithful', description: 'Accurately represents source' },
  { value: 'overbroad', label: 'Overbroad', description: 'Claims more than source supports' },
  { value: 'underspecified', label: 'Underspecified', description: 'Missing important qualifiers' },
  { value: 'wrong', label: 'Wrong', description: 'Misrepresents source' },
  { value: 'unsupported', label: 'Unsupported', description: 'No source basis for claim' },
];

export const GROUNDING_QUALITY_OPTIONS: { value: GroundingQuality; label: string; description: string }[] = [
  { value: 'sufficient', label: 'Sufficient', description: 'Span + context adequate' },
  { value: 'missing_context', label: 'Missing Context', description: 'Need more surrounding text' },
  { value: 'wrong_span', label: 'Wrong Span', description: 'Span boundaries incorrect' },
  { value: 'source_mismatch', label: 'Source Mismatch', description: "Span doesn't match source doc" },
];

export const EVIDENCE_USABILITY_OPTIONS: { value: EvidenceUsability; label: string; description: string }[] = [
  { value: 'argument_support', label: 'Argument Support', description: 'Could support main argument' },
  { value: 'rebuttal_support', label: 'Rebuttal Support', description: 'Could support rebuttal' },
  { value: 'context_only', label: 'Context Only', description: 'Background, not argumentative' },
  { value: 'unusable', label: 'Unusable', description: 'Cannot use in debate' },
];
