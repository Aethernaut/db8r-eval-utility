/**
 * SpanAnnotator - Overlay-based text span annotation component.
 *
 * Architecture:
 * - TextLayer: Plain text render (single textContent node)
 * - HighlightOverlay: Absolute-positioned boxes from Range.getClientRects()
 * - SelectionHandler: Click-drag to create spans
 * - ResizeHandles: Draggable handles on span edges
 * - SpanPopover: Delete / toggle is_claim_bearing / accept prefill
 *
 * Key features:
 * - Overlay-based highlights (NOT nested <span> elements)
 * - Word-snap default, Alt+drag for char-precise
 * - Virtualized for 50k+ char docs (only compute visible spans)
 * - Translucent stacking for overlaps
 */

import {
  useRef,
  useState,
  useEffect,
  useCallback,
  useMemo,
  type MouseEvent,
} from 'react';
import type { SpanAnnotatorProps, Span, HighlightRect, SelectionState } from './types';
import {
  getSpanRects,
  isSpanInViewport,
  snapToWordBoundaries,
  getOffsetFromPoint,
  findOverlappingSpans,
} from './utils';
import { SpanPopover } from './SpanPopover';
import { OverlapMenu } from './OverlapMenu';
import styles from './SpanAnnotator.module.css';

// Viewport buffer for virtualization (pixels above/below viewport)
const VIEWPORT_BUFFER = 200;

export function SpanAnnotator({
  sourceText,
  spans,
  mode,
  onCreate,
  onResize,
  onDelete,
  onToggle,
  onAcceptPrefill,
  spanQualityStates,
  onQualityChange,
}: SpanAnnotatorProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const textRef = useRef<HTMLDivElement>(null);
  const textNodeRef = useRef<Text | null>(null);

  // State
  const [selection, setSelection] = useState<SelectionState>({
    isSelecting: false,
    anchorOffset: 0,
    focusOffset: 0,
    isAltPressed: false,
  });
  const [highlightRects, setHighlightRects] = useState<HighlightRect[]>([]);
  const [selectedSpanId, setSelectedSpanId] = useState<string | null>(null);
  const [popoverPosition, setPopoverPosition] = useState<{ x: number; y: number } | null>(null);
  const [overlapMenuPosition, setOverlapMenuPosition] = useState<{ x: number; y: number } | null>(null);
  const [overlappingSpans, setOverlappingSpans] = useState<Span[]>([]);
  const [resizing, setResizing] = useState<{
    spanId: string;
    edge: 'start' | 'end';
    originalOffset: number;
    originalLength: number;
  } | null>(null);

  // Get text node reference
  useEffect(() => {
    if (textRef.current) {
      textNodeRef.current = textRef.current.firstChild as Text | null;
    }
  }, [sourceText]);

  // Compute visible highlights (virtualized)
  const computeHighlights = useCallback(() => {
    const container = containerRef.current;
    const textNode = textNodeRef.current;
    if (!container || !textNode) return;

    const containerRect = container.getBoundingClientRect();
    const scrollTop = container.scrollTop;
    const viewportTop = scrollTop - VIEWPORT_BUFFER;
    const viewportBottom = scrollTop + container.clientHeight + VIEWPORT_BUFFER;

    // Filter to visible spans only
    const visibleSpans = spans.filter((span) =>
      isSpanInViewport(span, textNode, viewportTop, viewportBottom, containerRect),
    );

    // Compute rects for visible spans
    const rects: HighlightRect[] = [];
    for (const span of visibleSpans) {
      const spanRects = getSpanRects(textNode, span, containerRect);
      rects.push(...spanRects);
    }

    setHighlightRects(rects);
  }, [spans]);

  // Recompute highlights on scroll/resize/spans change
  useEffect(() => {
    computeHighlights();
  }, [computeHighlights]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const handleScroll = () => computeHighlights();
    const handleResize = () => computeHighlights();

    container.addEventListener('scroll', handleScroll, { passive: true });
    window.addEventListener('resize', handleResize);

    return () => {
      container.removeEventListener('scroll', handleScroll);
      window.removeEventListener('resize', handleResize);
    };
  }, [computeHighlights]);

  // Track Alt key for char-precise mode
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Alt') {
        setSelection((s) => ({ ...s, isAltPressed: true }));
      }
    };
    const handleKeyUp = (e: KeyboardEvent) => {
      if (e.key === 'Alt') {
        setSelection((s) => ({ ...s, isAltPressed: false }));
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
    };
  }, []);

  // Selection handlers
  const handleMouseDown = useCallback(
    (e: MouseEvent) => {
      if (mode === 'readonly' || resizing) return;

      const textNode = textNodeRef.current;
      if (!textNode) return;

      const offset = getOffsetFromPoint(textNode, e.clientX, e.clientY);
      if (offset === null) return;

      // Check if clicking on an existing span
      const clickedSpans = findOverlappingSpans(spans, offset);

      if (clickedSpans.length > 1) {
        // Show overlap menu
        setOverlappingSpans(clickedSpans);
        setOverlapMenuPosition({ x: e.clientX, y: e.clientY });
        return;
      }

      if (clickedSpans.length === 1 && clickedSpans[0]) {
        // Select the span
        const span = clickedSpans[0];
        setSelectedSpanId(span.spanId);
        setPopoverPosition({ x: e.clientX, y: e.clientY });
        return;
      }

      // Start new selection
      setSelection({
        isSelecting: true,
        anchorOffset: offset,
        focusOffset: offset,
        isAltPressed: e.altKey,
      });
      setSelectedSpanId(null);
      setPopoverPosition(null);
    },
    [mode, spans, resizing],
  );

  const handleMouseMove = useCallback(
    (e: MouseEvent) => {
      if (!selection.isSelecting) return;

      const textNode = textNodeRef.current;
      if (!textNode) return;

      const offset = getOffsetFromPoint(textNode, e.clientX, e.clientY);
      if (offset === null) return;

      setSelection((s) => ({ ...s, focusOffset: offset, isAltPressed: e.altKey }));
    },
    [selection.isSelecting],
  );

  const handleMouseUp = useCallback(
    (e: MouseEvent) => {
      if (!selection.isSelecting) return;

      const textNode = textNodeRef.current;
      if (!textNode) return;

      const offset = getOffsetFromPoint(textNode, e.clientX, e.clientY);
      if (offset === null) {
        setSelection((s) => ({ ...s, isSelecting: false }));
        return;
      }

      // Determine selection range
      let start = Math.min(selection.anchorOffset, offset);
      let end = Math.max(selection.anchorOffset, offset);

      // Apply word snapping unless Alt is pressed
      [start, end] = snapToWordBoundaries(
        sourceText,
        start,
        end,
        selection.isAltPressed || e.altKey,
      );

      // Only create span if there's meaningful selection
      const selectedText = sourceText.slice(start, end).trim();
      if (selectedText.length > 0 && onCreate) {
        onCreate({
          charOffset: start,
          charLength: end - start,
          text: sourceText.slice(start, end),
        });
      }

      setSelection({
        isSelecting: false,
        anchorOffset: 0,
        focusOffset: 0,
        isAltPressed: false,
      });
    },
    [selection, sourceText, onCreate],
  );

  // Resize handlers
  const handleResizeStart = useCallback(
    (spanId: string, edge: 'start' | 'end', e: MouseEvent) => {
      e.stopPropagation();
      if (mode === 'readonly') return;

      const span = spans.find((s) => s.spanId === spanId);
      if (!span) return;

      setResizing({
        spanId,
        edge,
        originalOffset: span.charOffset,
        originalLength: span.charLength,
      });
    },
    [mode, spans],
  );

  const handleResizeMove = useCallback(
    (e: MouseEvent) => {
      if (!resizing) return;

      const textNode = textNodeRef.current;
      if (!textNode) return;

      const offset = getOffsetFromPoint(textNode, e.clientX, e.clientY);
      if (offset === null) return;

      const span = spans.find((s) => s.spanId === resizing.spanId);
      if (!span) return;

      let newOffset = span.charOffset;
      let newLength = span.charLength;

      if (resizing.edge === 'start') {
        // Adjust start position
        const endOffset = span.charOffset + span.charLength;
        newOffset = Math.min(offset, endOffset - 1);
        newLength = endOffset - newOffset;
      } else {
        // Adjust end position
        const newEnd = Math.max(offset, span.charOffset + 1);
        newLength = newEnd - span.charOffset;
      }

      // Apply word snapping
      if (!selection.isAltPressed) {
        if (resizing.edge === 'start') {
          [newOffset] = snapToWordBoundaries(sourceText, newOffset, newOffset, false);
          newLength = span.charOffset + span.charLength - newOffset;
        } else {
          const endOffset = span.charOffset + newLength;
          const [, snappedEnd] = snapToWordBoundaries(sourceText, endOffset, endOffset, false);
          newLength = snappedEnd - span.charOffset;
        }
      }

      if (onResize && newLength > 0) {
        onResize(resizing.spanId, newOffset, newLength);
      }
    },
    [resizing, spans, selection.isAltPressed, sourceText, onResize],
  );

  const handleResizeEnd = useCallback(() => {
    setResizing(null);
  }, []);

  // Global mouse handlers for resize
  useEffect(() => {
    if (!resizing) return;

    const handleMouseMove = (e: globalThis.MouseEvent) => {
      handleResizeMove(e as unknown as MouseEvent);
    };

    const handleMouseUp = () => {
      handleResizeEnd();
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [resizing, handleResizeMove, handleResizeEnd]);

  // Selection preview highlight
  const selectionPreview = useMemo(() => {
    if (!selection.isSelecting) return null;

    const textNode = textNodeRef.current;
    const container = containerRef.current;
    if (!textNode || !container) return null;

    let start = Math.min(selection.anchorOffset, selection.focusOffset);
    let end = Math.max(selection.anchorOffset, selection.focusOffset);

    // Apply word snapping for preview
    [start, end] = snapToWordBoundaries(sourceText, start, end, selection.isAltPressed);

    if (start === end) return null;

    try {
      const range = document.createRange();
      range.setStart(textNode, start);
      range.setEnd(textNode, end);

      const containerRect = container.getBoundingClientRect();
      const rects = range.getClientRects();
      const previewRects: Array<{ top: number; left: number; width: number; height: number }> = [];

      for (let i = 0; i < rects.length; i++) {
        const rect = rects[i];
        if (!rect) continue;
        previewRects.push({
          top: rect.top - containerRect.top + container.scrollTop,
          left: rect.left - containerRect.left,
          width: rect.width,
          height: rect.height,
        });
      }

      return previewRects;
    } catch {
      return null;
    }
  }, [selection, sourceText]);

  // Get selected span for popover
  const selectedSpan = useMemo(
    () => spans.find((s) => s.spanId === selectedSpanId) ?? null,
    [spans, selectedSpanId],
  );

  // Close menus on outside click
  const handleBackgroundClick = useCallback(() => {
    setSelectedSpanId(null);
    setPopoverPosition(null);
    setOverlapMenuPosition(null);
    setOverlappingSpans([]);
  }, []);

  // Render highlight class based on state
  const getHighlightClass = (rect: HighlightRect) => {
    const classes = [styles.highlight];

    if (rect.isPrefill) {
      classes.push(styles.prefill);
    } else if (rect.isClaimBearing === true) {
      classes.push(styles.claimBearing);
    } else if (rect.isClaimBearing === false) {
      classes.push(styles.notClaimBearing);
    } else {
      classes.push(styles.unreviewed);
    }

    if (rect.spanId === selectedSpanId) {
      classes.push(styles.selected);
    }

    return classes.join(' ');
  };

  return (
    <div
      ref={containerRef}
      className={styles.container}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
    >
      {/* Text layer */}
      <div ref={textRef} className={styles.textLayer}>
        {sourceText}
      </div>

      {/* Highlight overlay */}
      <div className={styles.highlightOverlay}>
        {highlightRects.map((rect, idx) => (
          <div
            key={`${rect.spanId}-${idx}`}
            className={getHighlightClass(rect)}
            style={{
              position: 'absolute',
              top: rect.top,
              left: rect.left,
              width: rect.width,
              height: rect.height,
            }}
          >
            {/* Resize handles (only on first rect of span, in edit mode) */}
            {mode === 'edit' &&
              idx === highlightRects.findIndex((r) => r.spanId === rect.spanId) && (
                <>
                  <div
                    className={styles.resizeHandleStart}
                    onMouseDown={(e) => handleResizeStart(rect.spanId, 'start', e)}
                  />
                  <div
                    className={styles.resizeHandleEnd}
                    onMouseDown={(e) => handleResizeStart(rect.spanId, 'end', e)}
                  />
                </>
              )}
          </div>
        ))}

        {/* Selection preview */}
        {selectionPreview?.map((rect, idx) => (
          <div
            key={`preview-${idx}`}
            className={styles.selectionPreview}
            style={{
              position: 'absolute',
              top: rect.top,
              left: rect.left,
              width: rect.width,
              height: rect.height,
            }}
          />
        ))}
      </div>

      {/* Span popover */}
      {selectedSpan && popoverPosition && (
        <SpanPopover
          span={selectedSpan}
          position={popoverPosition}
          onClose={handleBackgroundClick}
          onDelete={onDelete}
          onToggle={onToggle}
          onAcceptPrefill={onAcceptPrefill}
          mode={mode}
          initialQualityState={spanQualityStates?.get(selectedSpan.spanId)}
          onQualityChange={onQualityChange}
        />
      )}

      {/* Overlap menu */}
      {overlapMenuPosition && overlappingSpans.length > 1 && (
        <OverlapMenu
          spans={overlappingSpans}
          position={overlapMenuPosition}
          onSelect={(spanId) => {
            const span = spans.find((s) => s.spanId === spanId);
            if (span) {
              setSelectedSpanId(spanId);
              setPopoverPosition(overlapMenuPosition);
            }
            setOverlapMenuPosition(null);
            setOverlappingSpans([]);
          }}
          onClose={() => {
            setOverlapMenuPosition(null);
            setOverlappingSpans([]);
          }}
        />
      )}
    </div>
  );
}
