/**
 * SpanQualityPanel - Collects span-level quality labels.
 *
 * Used in T2 Span view (via SpanPopover) to assess:
 * - Extraction quality (faithful/overbroad/underspecified/wrong/unsupported)
 * - Grounding quality (sufficient/missing_context/wrong_span/source_mismatch)
 * - Evidence usability (argument_support/rebuttal_support/context_only/unusable)
 */

import { useState, useEffect } from 'react';
import type {
  ExtractionQuality,
  GroundingQuality,
  EvidenceUsability,
} from '@/types/qualityLabels';
import {
  EXTRACTION_QUALITY_OPTIONS,
  GROUNDING_QUALITY_OPTIONS,
  EVIDENCE_USABILITY_OPTIONS,
} from '@/types/qualityLabels';
import styles from './SpanQualityPanel.module.css';

export interface SpanQualityState {
  extractionQuality: ExtractionQuality | null;
  groundingQuality: GroundingQuality | null;
  evidenceUsability: EvidenceUsability | null;
}

interface SpanQualityPanelProps {
  initialState?: Partial<SpanQualityState>;
  onChange: (state: SpanQualityState) => void;
  disabled?: boolean;
  compact?: boolean; // For popover use
}

export function SpanQualityPanel({
  initialState,
  onChange,
  disabled = false,
  compact = false,
}: SpanQualityPanelProps) {
  const [extractionQuality, setExtractionQuality] = useState<ExtractionQuality | null>(
    initialState?.extractionQuality ?? null
  );
  const [groundingQuality, setGroundingQuality] = useState<GroundingQuality | null>(
    initialState?.groundingQuality ?? null
  );
  const [evidenceUsability, setEvidenceUsability] = useState<EvidenceUsability | null>(
    initialState?.evidenceUsability ?? null
  );

  // Sync with parent when state changes
  useEffect(() => {
    onChange({
      extractionQuality,
      groundingQuality,
      evidenceUsability,
    });
  }, [extractionQuality, groundingQuality, evidenceUsability, onChange]);

  return (
    <div className={`${styles.panel} ${compact ? styles.compact : ''}`}>
      {!compact && <h4 className={styles.panelTitle}>Span Quality Assessment</h4>}

      {/* Extraction Quality */}
      <div className={styles.section}>
        <label className={styles.sectionLabel}>Extraction Quality</label>
        <div className={styles.buttonGroup}>
          {EXTRACTION_QUALITY_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              className={`${styles.optionButton} ${extractionQuality === opt.value ? styles.selected : ''}`}
              onClick={() => setExtractionQuality(opt.value)}
              disabled={disabled}
              title={opt.description}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Grounding Quality */}
      <div className={styles.section}>
        <label className={styles.sectionLabel}>Grounding Quality</label>
        <div className={styles.buttonGroup}>
          {GROUNDING_QUALITY_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              className={`${styles.optionButton} ${groundingQuality === opt.value ? styles.selected : ''}`}
              onClick={() => setGroundingQuality(opt.value)}
              disabled={disabled}
              title={opt.description}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Evidence Usability */}
      <div className={styles.section}>
        <label className={styles.sectionLabel}>Evidence Usability</label>
        <div className={styles.buttonGroup}>
          {EVIDENCE_USABILITY_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              className={`${styles.optionButton} ${evidenceUsability === opt.value ? styles.selected : ''}`}
              onClick={() => setEvidenceUsability(opt.value)}
              disabled={disabled}
              title={opt.description}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
