/**
 * DocumentQualityPanel - Collects document-level quality labels.
 *
 * Used in T1 Retrieval view to assess:
 * - Document relevance (germane/partial/background/irrelevant)
 * - Claim relation (supports/contradicts/mixed/background/unclear)
 * - Source issues (paywall, attribution, staleness, etc.)
 * - Corroboration status (independent/same_cluster/duplicate)
 */

import { useState, useEffect } from 'react';
import type {
  DocumentRelevance,
  ClaimRelation,
  SourceIssue,
  CorroborationStatus,
} from '@/types/qualityLabels';
import {
  DOCUMENT_RELEVANCE_OPTIONS,
  CLAIM_RELATION_OPTIONS,
  SOURCE_ISSUE_OPTIONS,
  CORROBORATION_OPTIONS,
} from '@/types/qualityLabels';
import styles from './DocumentQualityPanel.module.css';

export interface DocumentQualityState {
  relevance: DocumentRelevance | null;
  claimRelation: ClaimRelation | null;
  sourceIssues: SourceIssue[];
  corroborationStatus: CorroborationStatus | null;
}

interface DocumentQualityPanelProps {
  initialState?: Partial<DocumentQualityState>;
  onChange: (state: DocumentQualityState) => void;
  disabled?: boolean;
}

export function DocumentQualityPanel({
  initialState,
  onChange,
  disabled = false,
}: DocumentQualityPanelProps) {
  const [relevance, setRelevance] = useState<DocumentRelevance | null>(
    initialState?.relevance ?? null
  );
  const [claimRelation, setClaimRelation] = useState<ClaimRelation | null>(
    initialState?.claimRelation ?? null
  );
  const [sourceIssues, setSourceIssues] = useState<SourceIssue[]>(
    initialState?.sourceIssues ?? []
  );
  const [corroborationStatus, setCorroborationStatus] = useState<CorroborationStatus | null>(
    initialState?.corroborationStatus ?? null
  );

  // Sync with parent when state changes
  useEffect(() => {
    onChange({
      relevance,
      claimRelation,
      sourceIssues,
      corroborationStatus,
    });
  }, [relevance, claimRelation, sourceIssues, corroborationStatus, onChange]);

  const handleSourceIssueToggle = (issue: SourceIssue) => {
    if (issue === 'none') {
      setSourceIssues(['none']);
    } else {
      setSourceIssues((prev) => {
        const filtered = prev.filter((i) => i !== 'none');
        if (filtered.includes(issue)) {
          return filtered.filter((i) => i !== issue);
        }
        return [...filtered, issue];
      });
    }
  };

  return (
    <div className={styles.panel}>
      <h4 className={styles.panelTitle}>Evidence Quality Assessment</h4>

      {/* Relevance */}
      <div className={styles.section}>
        <label className={styles.sectionLabel}>Document Relevance</label>
        <div className={styles.buttonGroup}>
          {DOCUMENT_RELEVANCE_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              className={`${styles.optionButton} ${relevance === opt.value ? styles.selected : ''}`}
              onClick={() => setRelevance(opt.value)}
              disabled={disabled}
              title={opt.description}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Claim Relation */}
      <div className={styles.section}>
        <label className={styles.sectionLabel}>Relation to Claim</label>
        <div className={styles.buttonGroup}>
          {CLAIM_RELATION_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              className={`${styles.optionButton} ${claimRelation === opt.value ? styles.selected : ''}`}
              onClick={() => setClaimRelation(opt.value)}
              disabled={disabled}
              title={opt.description}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Source Issues */}
      <div className={styles.section}>
        <label className={styles.sectionLabel}>Source Issues</label>
        <div className={styles.checkboxGroup}>
          {SOURCE_ISSUE_OPTIONS.map((opt) => (
            <label
              key={opt.value}
              className={`${styles.checkboxLabel} ${sourceIssues.includes(opt.value) ? styles.checked : ''}`}
              title={opt.description}
            >
              <input
                type="checkbox"
                checked={sourceIssues.includes(opt.value)}
                onChange={() => handleSourceIssueToggle(opt.value)}
                disabled={disabled}
              />
              {opt.label}
            </label>
          ))}
        </div>
      </div>

      {/* Corroboration Status */}
      <div className={styles.section}>
        <label className={styles.sectionLabel}>Corroboration</label>
        <div className={styles.buttonGroup}>
          {CORROBORATION_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              className={`${styles.optionButton} ${corroborationStatus === opt.value ? styles.selected : ''}`}
              onClick={() => setCorroborationStatus(opt.value)}
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
