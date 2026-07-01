/**
 * Utility functions for SpanAnnotator.
 */

import type { Span, HighlightRect } from './types';

/**
 * Find word boundary by expanding from a character offset.
 * Returns [start, end] offsets.
 */
export function expandToWordBoundary(
  text: string,
  offset: number,
  direction: 'start' | 'end',
): number {
  const isWordChar = (c: string) => /\w/.test(c);

  if (direction === 'start') {
    // Move backward to start of word
    let pos = offset;
    while (pos > 0 && isWordChar(text[pos - 1] ?? '')) {
      pos--;
    }
    return pos;
  } else {
    // Move forward to end of word
    let pos = offset;
    while (pos < text.length && isWordChar(text[pos] ?? '')) {
      pos++;
    }
    return pos;
  }
}

/**
 * Snap selection to word boundaries (unless Alt is held for char-precise).
 */
export function snapToWordBoundaries(
  text: string,
  start: number,
  end: number,
  charPrecise: boolean,
): [number, number] {
  if (charPrecise) {
    return [start, end];
  }

  const snappedStart = expandToWordBoundary(text, start, 'start');
  const snappedEnd = expandToWordBoundary(text, end, 'end');

  return [snappedStart, snappedEnd];
}

/**
 * Convert a text offset to a position in the DOM text node.
 */
export function createRangeFromOffsets(
  textNode: Text,
  startOffset: number,
  endOffset: number,
): Range {
  const range = document.createRange();
  const textLength = textNode.textContent?.length ?? 0;

  // Clamp to valid offsets
  const start = Math.max(0, Math.min(startOffset, textLength));
  const end = Math.max(start, Math.min(endOffset, textLength));

  range.setStart(textNode, start);
  range.setEnd(textNode, end);
  return range;
}

/**
 * Get client rects from a span in the document.
 * Returns an array of DOMRect representing each line of the span.
 */
export function getSpanRects(
  textNode: Text,
  span: Span,
  containerRect: DOMRect,
): HighlightRect[] {
  try {
    const range = createRangeFromOffsets(
      textNode,
      span.charOffset,
      span.charOffset + span.charLength,
    );
    const rects = range.getClientRects();
    const highlights: HighlightRect[] = [];

    for (let i = 0; i < rects.length; i++) {
      const rect = rects[i];
      if (!rect) continue;

      highlights.push({
        spanId: span.spanId,
        top: rect.top - containerRect.top,
        left: rect.left - containerRect.left,
        width: rect.width,
        height: rect.height,
        isClaimBearing: span.isClaimBearing,
        isPrefill: span.labelSource === 'pipeline_prefill',
      });
    }

    return highlights;
  } catch {
    return [];
  }
}

/**
 * Check if a span is visible in the viewport.
 */
export function isSpanInViewport(
  span: Span,
  textNode: Text,
  viewportTop: number,
  viewportBottom: number,
  containerRect: DOMRect,
): boolean {
  try {
    const range = createRangeFromOffsets(
      textNode,
      span.charOffset,
      span.charOffset + span.charLength,
    );
    const rects = range.getClientRects();

    for (let i = 0; i < rects.length; i++) {
      const rect = rects[i];
      if (!rect) continue;
      const relativeTop = rect.top - containerRect.top;
      const relativeBottom = rect.bottom - containerRect.top;

      // Check if any part of the rect is in viewport
      if (relativeBottom >= viewportTop && relativeTop <= viewportBottom) {
        return true;
      }
    }
    return false;
  } catch {
    return false;
  }
}

/**
 * Find overlapping spans at a given point.
 */
export function findOverlappingSpans(
  spans: Span[],
  charOffset: number,
): Span[] {
  return spans.filter(
    (span) =>
      charOffset >= span.charOffset &&
      charOffset < span.charOffset + span.charLength,
  );
}

// Extend Document interface for caretPositionFromPoint (not in all TS DOM types)
interface CaretPosition {
  offsetNode: Node | null;
  offset: number;
}

interface DocumentWithCaretPosition extends Document {
  caretPositionFromPoint?: (x: number, y: number) => CaretPosition | null;
}

/**
 * Get the text offset from a mouse position.
 */
export function getOffsetFromPoint(
  textNode: Text,
  x: number,
  y: number,
): number | null {
  const doc = document as DocumentWithCaretPosition;

  // Use caretPositionFromPoint or caretRangeFromPoint
  if (doc.caretPositionFromPoint) {
    const pos = doc.caretPositionFromPoint(x, y);
    if (pos?.offsetNode === textNode) {
      return pos.offset;
    }
    // Walk up to find if we're in the text container
    let node = pos?.offsetNode;
    while (node) {
      if (node === textNode || node.parentNode?.contains(textNode)) {
        return pos?.offset ?? null;
      }
      node = node.parentNode as Node | null;
    }
  }

  // Fallback for older browsers
  if (document.caretRangeFromPoint) {
    const range = document.caretRangeFromPoint(x, y);
    if (range?.startContainer === textNode) {
      return range.startOffset;
    }
  }

  return null;
}
