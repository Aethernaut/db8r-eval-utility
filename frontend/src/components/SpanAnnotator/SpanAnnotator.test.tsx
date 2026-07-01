import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { SpanAnnotator } from './SpanAnnotator';
import type { Span } from './types';

describe('SpanAnnotator', () => {
  const sampleText = 'This is a sample text for testing span annotation capabilities.';

  const sampleSpans: Span[] = [
    {
      spanId: 'span-1',
      charOffset: 10,
      charLength: 6,
      text: 'sample',
      isClaimBearing: true,
      labelSource: 'human_authored',
    },
    {
      spanId: 'span-2',
      charOffset: 22,
      charLength: 7,
      text: 'testing',
      isClaimBearing: false,
      labelSource: 'human_authored',
    },
    {
      spanId: 'span-3',
      charOffset: 35,
      charLength: 4,
      text: 'span',
      isClaimBearing: null,
      labelSource: 'pipeline_prefill',
    },
  ];

  it('renders the source text', () => {
    render(
      <SpanAnnotator
        sourceText={sampleText}
        spans={[]}
        mode="readonly"
      />,
    );

    expect(screen.getByText(sampleText)).toBeInTheDocument();
  });

  it('renders in readonly mode without handlers', () => {
    const { container } = render(
      <SpanAnnotator
        sourceText={sampleText}
        spans={sampleSpans}
        mode="readonly"
      />,
    );

    // Should render without errors
    expect(container.querySelector('[class*="container"]')).toBeInTheDocument();
  });

  it('renders in edit mode with handlers', () => {
    const onCreate = vi.fn();
    const onDelete = vi.fn();
    const onToggle = vi.fn();

    const { container } = render(
      <SpanAnnotator
        sourceText={sampleText}
        spans={sampleSpans}
        mode="edit"
        onCreate={onCreate}
        onDelete={onDelete}
        onToggle={onToggle}
      />,
    );

    // Should render without errors
    expect(container.querySelector('[class*="container"]')).toBeInTheDocument();
  });

  it('handles empty spans array', () => {
    const { container } = render(
      <SpanAnnotator
        sourceText={sampleText}
        spans={[]}
        mode="edit"
      />,
    );

    expect(container.querySelector('[class*="container"]')).toBeInTheDocument();
  });

  it('handles large text content', () => {
    // Generate 50k+ character text
    const largeText = 'Lorem ipsum dolor sit amet. '.repeat(2000);

    const { container } = render(
      <SpanAnnotator
        sourceText={largeText}
        spans={[]}
        mode="readonly"
      />,
    );

    expect(container.querySelector('[class*="textLayer"]')).toBeInTheDocument();
  });
});
