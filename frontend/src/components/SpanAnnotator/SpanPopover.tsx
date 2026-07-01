/**
 * SpanPopover - Contextual menu for span actions.
 */

import { useEffect, useRef, useState } from 'react';
import type { Span, SpanAnnotatorMode } from './types';
import { Button } from '@/components/ui/Button';
import { SpanQualityPanel, type SpanQualityState } from '@/components/QualityLabels';
import styles from './SpanPopover.module.css';

interface SpanPopoverProps {
  span: Span;
  position: { x: number; y: number };
  mode: SpanAnnotatorMode;
  initialQualityState?: Partial<SpanQualityState>;
  onClose: () => void;
  onDelete?: (spanId: string) => void;
  onToggle?: (spanId: string, isClaimBearing: boolean) => void;
  onAcceptPrefill?: (spanId: string) => void;
  onQualityChange?: (spanId: string, state: SpanQualityState) => void;
}

export function SpanPopover({
  span,
  position,
  mode,
  initialQualityState,
  onClose,
  onDelete,
  onToggle,
  onAcceptPrefill,
  onQualityChange,
}: SpanPopoverProps) {
  const popoverRef = useRef<HTMLDivElement>(null);
  const [showQualityPanel, setShowQualityPanel] = useState(false);

  // Close on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        onClose();
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [onClose]);

  // Close on escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  const isPrefill = span.labelSource === 'pipeline_prefill';
  const isEditable = mode === 'edit';

  // Determine button states
  const showClaimBearingToggle = isEditable && !isPrefill;
  const showAcceptPrefill = isEditable && isPrefill;
  const showDelete = isEditable;

  return (
    <div
      ref={popoverRef}
      className={styles.popover}
      style={{
        position: 'fixed',
        top: position.y + 10,
        left: position.x,
      }}
    >
      {/* Span text preview */}
      <div className={styles.textPreview} title={span.text}>
        {span.text.length > 60 ? span.text.slice(0, 60) + '...' : span.text}
      </div>

      {/* Status indicator */}
      <div className={styles.status}>
        {isPrefill && <span className={styles.badge + ' ' + styles.prefillBadge}>Prefill</span>}
        {span.isClaimBearing === true && (
          <span className={styles.badge + ' ' + styles.claimBearingBadge}>Claim-bearing</span>
        )}
        {span.isClaimBearing === false && (
          <span className={styles.badge + ' ' + styles.notClaimBearingBadge}>Not claim-bearing</span>
        )}
        {span.isClaimBearing === null && !isPrefill && (
          <span className={styles.badge + ' ' + styles.unreviewedBadge}>Unreviewed</span>
        )}
      </div>

      {/* CC-4: Attribution metadata */}
      {span.claimantName && (
        <div className={styles.attribution}>
          <span className={styles.attrLabel}>Claimant:</span>
          <span className={styles.attrValue}>{span.claimantName}</span>
          {span.attributionType && (
            <span className={styles.attrType}>({span.attributionType})</span>
          )}
        </div>
      )}

      {/* Actions */}
      {isEditable && (
        <div className={styles.actions}>
          {showAcceptPrefill && onAcceptPrefill && (
            <Button
              size="sm"
              variant="primary"
              onClick={() => {
                onAcceptPrefill(span.spanId);
                onClose();
              }}
            >
              Accept Prefill
            </Button>
          )}

          {showClaimBearingToggle && onToggle && (
            <>
              {span.isClaimBearing !== true && (
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => {
                    onToggle(span.spanId, true);
                    onClose();
                  }}
                >
                  Mark Claim-bearing
                </Button>
              )}
              {span.isClaimBearing !== false && (
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => {
                    onToggle(span.spanId, false);
                    onClose();
                  }}
                >
                  Mark Not Claim-bearing
                </Button>
              )}
            </>
          )}

          {showDelete && onDelete && (
            <Button
              size="sm"
              variant="danger"
              onClick={() => {
                onDelete(span.spanId);
                onClose();
              }}
            >
              Delete
            </Button>
          )}

          {onQualityChange && (
            <Button
              size="sm"
              variant="secondary"
              onClick={() => setShowQualityPanel(!showQualityPanel)}
            >
              {showQualityPanel ? 'Hide' : 'Show'} Quality Labels
            </Button>
          )}
        </div>
      )}

      {/* Span Quality Labels Panel */}
      {showQualityPanel && onQualityChange && (
        <SpanQualityPanel
          initialState={initialQualityState}
          onChange={(state) => onQualityChange(span.spanId, state)}
          compact
        />
      )}
    </div>
  );
}
