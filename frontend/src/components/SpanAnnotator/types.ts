/**
 * Types for the SpanAnnotator component.
 */

export interface Span {
  spanId: string;
  charOffset: number;
  charLength: number;
  text: string;
  isClaimBearing: boolean | null;
  labelSource: 'pipeline_prefill' | 'pipeline_prefill_corrected' | 'human_authored' | null;
  // CC-4: Claim Attribution metadata
  claimantName?: string | null;
  claimantKey?: string | null;
  attributionType?: string | null;
}

export interface SpanCreateData {
  charOffset: number;
  charLength: number;
  text: string;
}

export type SpanAnnotatorMode = 'edit' | 'readonly';

/** Quality state for a span (extraction, grounding, evidence usability) */
export interface SpanQualityState {
  extractionQuality: 'faithful' | 'overbroad' | 'underspecified' | 'wrong' | 'unsupported' | null;
  groundingQuality: 'sufficient' | 'missing_context' | 'wrong_span' | 'source_mismatch' | null;
  evidenceUsability: 'argument_support' | 'rebuttal_support' | 'context_only' | 'unusable' | null;
}

export interface SpanAnnotatorProps {
  /** The source text to annotate */
  sourceText: string;
  /** Existing spans to render */
  spans: Span[];
  /** Whether the annotator is editable or read-only */
  mode: SpanAnnotatorMode;
  /** Callback when a new span is created via selection */
  onCreate?: (span: SpanCreateData) => void;
  /** Callback when a span is resized via drag handles */
  onResize?: (spanId: string, newOffset: number, newLength: number) => void;
  /** Callback when a span is deleted */
  onDelete?: (spanId: string) => void;
  /** Callback when a span's is_claim_bearing status is toggled */
  onToggle?: (spanId: string, isClaimBearing: boolean) => void;
  /** Callback when a prefilled span is accepted */
  onAcceptPrefill?: (spanId: string) => void;
  /** Map of span quality states (spanId -> state) */
  spanQualityStates?: Map<string, SpanQualityState>;
  /** Callback when span quality labels change */
  onQualityChange?: (spanId: string, state: SpanQualityState) => void;
}

/** Internal representation of a highlight box */
export interface HighlightRect {
  spanId: string;
  top: number;
  left: number;
  width: number;
  height: number;
  isClaimBearing: boolean | null;
  isPrefill: boolean;
}

/** Selection state during drag */
export interface SelectionState {
  isSelecting: boolean;
  anchorOffset: number;
  focusOffset: number;
  isAltPressed: boolean; // char-precise mode
}
