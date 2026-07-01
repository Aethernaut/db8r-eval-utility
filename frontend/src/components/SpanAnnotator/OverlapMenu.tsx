/**
 * OverlapMenu - Chip menu for disambiguating overlapping spans.
 */

import { useEffect, useRef } from 'react';
import type { Span } from './types';
import styles from './OverlapMenu.module.css';

interface OverlapMenuProps {
  spans: Span[];
  position: { x: number; y: number };
  onSelect: (spanId: string) => void;
  onClose: () => void;
}

export function OverlapMenu({ spans, position, onSelect, onClose }: OverlapMenuProps) {
  const menuRef = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
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

  const getChipClass = (span: Span) => {
    const classes = [styles.chip];

    if (span.labelSource === 'pipeline_prefill') {
      classes.push(styles.prefill);
    } else if (span.isClaimBearing === true) {
      classes.push(styles.claimBearing);
    } else if (span.isClaimBearing === false) {
      classes.push(styles.notClaimBearing);
    } else {
      classes.push(styles.unreviewed);
    }

    return classes.join(' ');
  };

  const truncateText = (text: string, maxLength: number = 25) => {
    if (text.length <= maxLength) return text;
    return text.slice(0, maxLength) + '...';
  };

  return (
    <div
      ref={menuRef}
      className={styles.menu}
      style={{
        position: 'fixed',
        top: position.y + 10,
        left: position.x,
      }}
    >
      <div className={styles.title}>Select span:</div>
      <div className={styles.chips}>
        {spans.map((span) => (
          <button
            key={span.spanId}
            className={getChipClass(span)}
            onClick={() => onSelect(span.spanId)}
            title={span.text}
          >
            {truncateText(span.text)}
          </button>
        ))}
      </div>
    </div>
  );
}
