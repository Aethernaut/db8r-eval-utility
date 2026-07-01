import { clsx, type ClassValue } from 'clsx';

/**
 * Utility for combining class names (clsx wrapper).
 */
export function cn(...inputs: ClassValue[]): string {
  return clsx(inputs);
}

/**
 * Format a date string for display.
 */
export function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

/**
 * Format a date string with time for display.
 */
export function formatDateTime(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/**
 * Truncate text with ellipsis.
 */
export function truncate(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength - 3) + '...';
}

/**
 * Debounce function calls.
 */
export function debounce<T extends (...args: unknown[]) => void>(
  fn: T,
  delay: number,
): (...args: Parameters<T>) => void {
  let timeoutId: ReturnType<typeof setTimeout>;
  return (...args: Parameters<T>) => {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => fn(...args), delay);
  };
}

/**
 * Calculate character range IoU (Intersection over Union).
 * Used for span matching.
 */
export function charRangeIoU(
  aOffset: number,
  aLength: number,
  bOffset: number,
  bLength: number,
): number {
  const aEnd = aOffset + aLength;
  const bEnd = bOffset + bLength;

  const intersectionStart = Math.max(aOffset, bOffset);
  const intersectionEnd = Math.min(aEnd, bEnd);
  const intersection = Math.max(0, intersectionEnd - intersectionStart);

  const union = aLength + bLength - intersection;

  if (union === 0) return 0;
  return intersection / union;
}
