import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, useBlocker } from 'react-router';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiGet, apiPost, apiPut, apiDelete } from '@/api/client';
import { SpanAnnotator, type Span, type SpanCreateData, type SpanQualityState } from '@/components/SpanAnnotator';
import { Button } from '@/components/ui/Button';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import type { SpanQualityLabel } from '@/types/qualityLabels';
import styles from './T2SpanPage.module.css';

interface FixtureDocumentResponse {
  document_id: string;
  source_url: string;
  source_title: string | null;
  source_text_hash: string;
  source_text: string;
  source_text_char_len: number;
  source_reliability: number | null;
  // CC-4: MBFC Source Reliability metadata
  publisher_name: string | null;
  publisher_mbfc_key: string | null;
  mbfc_factual_rating: string | null;
  mbfc_bias_rating: string | null;
}

// CC-4: Helper to format reliability badge
function formatReliability(score: number | null | undefined): { label: string; className: string } | null {
  if (score == null) return null;
  if (score >= 0.8) return { label: 'High', className: 'reliabilityHigh' };
  if (score >= 0.6) return { label: 'Medium', className: 'reliabilityMedium' };
  return { label: 'Low', className: 'reliabilityLow' };
}

interface GoldSpanResponse {
  span_id: string;
  document_id: string;
  fixture_id: string;
  char_offset: number;
  char_length: number;
  text: string;
  is_claim_bearing: boolean | null;
  label_source: string | null;
  // CC-4: Claim Attribution metadata
  claimant_name: string | null;
  claimant_key: string | null;
  attribution_type: string | null;
}

interface GoldSpanListResponse {
  spans: GoldSpanResponse[];
  total: number;
}

interface DocumentAnnotationResponse {
  document_id: string;
  exhaustively_annotated: boolean;
  lost_evidence_flag: boolean;
  lost_evidence_note: string | null;
}

interface SpanQualityLabelResponse {
  id: string;
  span_id: string;
  extraction_quality: string | null;
  grounding_quality: string | null;
  evidence_usability: string | null;
}

interface SpanQualityLabelListResponse {
  labels: SpanQualityLabelResponse[];
  total: number;
}

// Extended response type that includes fixture_id
interface NextDocumentResponse extends FixtureDocumentResponse {
  fixture_id: string;
}

export function T2SpanPage() {
  const { documentId: rawDocumentId } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [exhaustivelyAnnotated, setExhaustivelyAnnotated] = useState(false);
  const [lostEvidenceFlag, setLostEvidenceFlag] = useState(false);
  const [spanQualityStates, setSpanQualityStates] = useState<Map<string, SpanQualityState>>(new Map());

  // Handle "next" special case - fetch next unannotated document and redirect
  const nextDocQuery = useQuery({
    queryKey: ['next-document'],
    queryFn: () => apiGet<NextDocumentResponse>('/api/v1/fixtures/documents/next'),
    enabled: rawDocumentId === 'next',
    retry: false,
  });

  // Redirect to actual document ID when "next" resolves
  useEffect(() => {
    if (rawDocumentId === 'next' && nextDocQuery.data) {
      navigate(`/t2/${nextDocQuery.data.source_text_hash}`, { replace: true });
    }
  }, [rawDocumentId, nextDocQuery.data, navigate]);

  // Use the actual document ID (not "next")
  const documentId = rawDocumentId === 'next' ? undefined : rawDocumentId;

  // Block navigation if unsaved changes
  const blocker = useBlocker(hasUnsavedChanges);

  useEffect(() => {
    if (blocker.state === 'blocked') {
      const shouldLeave = window.confirm(
        'You have unsaved changes. Are you sure you want to leave?',
      );
      if (shouldLeave) {
        blocker.proceed();
      } else {
        blocker.reset();
      }
    }
  }, [blocker]);

  // Fetch document (we need the fixture ID and source_text_hash)
  // For now, we'll assume documentId is the source_text_hash
  const documentQuery = useQuery({
    queryKey: ['document', documentId],
    queryFn: async () => {
      // Search fixtures for this document
      const fixtures = await apiGet<{ fixtures: Array<{ fixture_id: string }> }>(
        '/api/v1/fixtures?limit=50',
      );

      // Try each fixture to find the document
      for (const fixture of fixtures.fixtures) {
        try {
          const doc = await apiGet<FixtureDocumentResponse>(
            `/api/v1/fixtures/${fixture.fixture_id}/documents/${documentId}`,
          );
          return { ...doc, fixture_id: fixture.fixture_id };
        } catch {
          // Not found in this fixture, try next
        }
      }
      throw new Error('Document not found');
    },
    enabled: !!documentId && documentId !== 'next',
  });

  // Fetch spans for this document
  const spansQuery = useQuery({
    queryKey: ['spans', documentId],
    queryFn: () =>
      apiGet<GoldSpanListResponse>(`/api/v1/spans?document_id=${documentId}&limit=500`),
    enabled: !!documentId && documentId !== 'next',
  });

  // Fetch document annotation state
  const annotationQuery = useQuery({
    queryKey: ['document-annotation', documentId],
    queryFn: () =>
      apiGet<DocumentAnnotationResponse>(`/api/v1/documents/${documentId}/annotation`),
    enabled: !!documentId && documentId !== 'next',
  });

  // Fetch span quality labels for this document
  const spanQualityQuery = useQuery({
    queryKey: ['span-quality-labels', documentId],
    queryFn: () =>
      apiGet<SpanQualityLabelListResponse>(`/api/v1/quality-labels/spans?document_id=${documentId}&limit=500`),
    enabled: !!documentId && documentId !== 'next',
  });

  // Initialize span quality states from existing data
  useEffect(() => {
    if (spanQualityQuery.data?.labels) {
      const initial = new Map<string, SpanQualityState>();
      for (const label of spanQualityQuery.data.labels) {
        initial.set(label.span_id, {
          extractionQuality: label.extraction_quality as SpanQualityState['extractionQuality'],
          groundingQuality: label.grounding_quality as SpanQualityState['groundingQuality'],
          evidenceUsability: label.evidence_usability as SpanQualityState['evidenceUsability'],
        });
      }
      setSpanQualityStates(initial);
    }
  }, [spanQualityQuery.data]);

  // Update local state when annotation loads
  useEffect(() => {
    if (annotationQuery.data) {
      setExhaustivelyAnnotated(annotationQuery.data.exhaustively_annotated);
      setLostEvidenceFlag(annotationQuery.data.lost_evidence_flag);
    }
  }, [annotationQuery.data]);

  // Mutations
  const createSpanMutation = useMutation({
    mutationFn: (data: {
      document_id: string;
      fixture_id: string;
      char_offset: number;
      char_length: number;
      text: string;
    }) => apiPost<GoldSpanResponse>('/api/v1/spans', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['spans', documentId] });
      setHasUnsavedChanges(false);
    },
  });

  const updateSpanMutation = useMutation({
    mutationFn: ({
      spanId,
      data,
    }: {
      spanId: string;
      data: { is_claim_bearing?: boolean; label_source?: string };
    }) => apiPut<GoldSpanResponse>(`/api/v1/spans/${spanId}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['spans', documentId] });
      setHasUnsavedChanges(false);
    },
  });

  const deleteSpanMutation = useMutation({
    mutationFn: (spanId: string) => apiDelete(`/api/v1/spans/${spanId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['spans', documentId] });
      setHasUnsavedChanges(false);
    },
  });

  const updateDocumentMutation = useMutation({
    mutationFn: (data: {
      exhaustively_annotated?: boolean;
      lost_evidence_flag?: boolean;
    }) => apiPut<DocumentAnnotationResponse>(`/api/v1/documents/${documentId}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['document-annotation', documentId] });
    },
  });

  const prefillMutation = useMutation({
    mutationFn: (data: { fixture_id: string; document_id: string }) =>
      apiPost('/api/v1/spans/prefill', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['spans', documentId] });
    },
  });

  // Save span quality label mutation
  const saveSpanQualityMutation = useMutation({
    mutationFn: (data: {
      span_id: string;
      extraction_quality: string | null;
      grounding_quality: string | null;
      evidence_usability: string | null;
    }) => apiPost<SpanQualityLabel>('/api/v1/quality-labels/spans', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['span-quality-labels', documentId] });
    },
  });

  // Convert API spans to component spans
  const spans: Span[] = (spansQuery.data?.spans ?? []).map((s) => ({
    spanId: s.span_id,
    charOffset: s.char_offset,
    charLength: s.char_length,
    text: s.text,
    isClaimBearing: s.is_claim_bearing,
    labelSource: s.label_source as Span['labelSource'],
    // CC-4: Claim Attribution metadata
    claimantName: s.claimant_name,
    claimantKey: s.claimant_key,
    attributionType: s.attribution_type,
  }));

  // Handlers
  const handleCreate = useCallback(
    (spanData: SpanCreateData) => {
      if (!documentQuery.data) return;
      createSpanMutation.mutate({
        document_id: documentId ?? '',
        fixture_id: documentQuery.data.fixture_id,
        char_offset: spanData.charOffset,
        char_length: spanData.charLength,
        text: spanData.text,
      });
    },
    [documentId, documentQuery.data, createSpanMutation],
  );

  const handleResize = useCallback(
    (spanId: string, newOffset: number, newLength: number) => {
      // Resize requires delete + create (API doesn't support offset updates)
      const span = spansQuery.data?.spans.find((s) => s.span_id === spanId);
      if (!span || !documentQuery.data) return;

      const newText =
        documentQuery.data.source_text.slice(newOffset, newOffset + newLength);

      deleteSpanMutation.mutate(spanId, {
        onSuccess: () => {
          createSpanMutation.mutate({
            document_id: documentId ?? '',
            fixture_id: documentQuery.data!.fixture_id,
            char_offset: newOffset,
            char_length: newLength,
            text: newText,
          });
        },
      });
    },
    [documentId, documentQuery.data, spansQuery.data, createSpanMutation, deleteSpanMutation],
  );

  const handleDelete = useCallback(
    (spanId: string) => {
      deleteSpanMutation.mutate(spanId);
    },
    [deleteSpanMutation],
  );

  const handleToggle = useCallback(
    (spanId: string, isClaimBearing: boolean) => {
      updateSpanMutation.mutate({
        spanId,
        data: { is_claim_bearing: isClaimBearing, label_source: 'human_authored' },
      });
    },
    [updateSpanMutation],
  );

  const handleAcceptPrefill = useCallback(
    (spanId: string) => {
      updateSpanMutation.mutate({
        spanId,
        data: { label_source: 'pipeline_prefill_corrected' },
      });
    },
    [updateSpanMutation],
  );

  const handlePrefill = useCallback(() => {
    if (!documentQuery.data) return;
    prefillMutation.mutate({
      fixture_id: documentQuery.data.fixture_id,
      document_id: documentId ?? '',
    });
  }, [documentId, documentQuery.data, prefillMutation]);

  const handleQualityChange = useCallback((spanId: string, state: SpanQualityState) => {
    // Update local state
    setSpanQualityStates((prev) => {
      const next = new Map(prev);
      next.set(spanId, state);
      return next;
    });

    // Save to API
    if (state.extractionQuality || state.groundingQuality || state.evidenceUsability) {
      saveSpanQualityMutation.mutate({
        span_id: spanId,
        extraction_quality: state.extractionQuality,
        grounding_quality: state.groundingQuality,
        evidence_usability: state.evidenceUsability,
      });
    }
  }, [saveSpanQualityMutation]);

  const handleSaveFlags = useCallback(() => {
    updateDocumentMutation.mutate({
      exhaustively_annotated: exhaustivelyAnnotated,
      lost_evidence_flag: lostEvidenceFlag,
    });
  }, [exhaustivelyAnnotated, lostEvidenceFlag, updateDocumentMutation]);

  // Loading state: either waiting for "next" redirect or loading document data
  if (rawDocumentId === 'next' && nextDocQuery.isLoading) {
    return (
      <div className={styles.loading}>
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  // Error state: no documents need annotation
  if (rawDocumentId === 'next' && nextDocQuery.error) {
    return (
      <div className={styles.error}>
        <h2>No documents to annotate</h2>
        <p>All documents have been exhaustively annotated.</p>
        <Button onClick={() => navigate('/')}>Return to Dashboard</Button>
      </div>
    );
  }

  // Still waiting for redirect when documentId is "next"
  if (rawDocumentId === 'next') {
    return (
      <div className={styles.loading}>
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  // Loading state
  if (documentQuery.isLoading || spansQuery.isLoading) {
    return (
      <div className={styles.loading}>
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  // Error state
  if (documentQuery.error || !documentQuery.data) {
    return (
      <div className={styles.error}>
        <h2>Document not found</h2>
        <p>Could not load document with ID: {documentId}</p>
        <Button onClick={() => navigate('/')}>Return to Dashboard</Button>
      </div>
    );
  }

  const doc = documentQuery.data;

  return (
    <div className={styles.page}>
      {/* Header */}
      <div className={styles.header}>
        <div className={styles.headerContent}>
          <h1 className={styles.title}>{doc.source_title ?? 'Untitled Document'}</h1>
          <a href={doc.source_url} target="_blank" rel="noopener noreferrer" className={styles.url}>
            {doc.source_url}
          </a>
        </div>
        <div className={styles.headerActions}>
          <Button variant="secondary" size="sm" onClick={handlePrefill} disabled={prefillMutation.isPending}>
            {prefillMutation.isPending ? 'Importing...' : 'Import Prefill'}
          </Button>
        </div>
      </div>

      {/* Document info */}
      <div className={styles.info}>
        <span className={styles.infoBadge}>{doc.source_text_char_len.toLocaleString()} chars</span>
        <span className={styles.infoBadge}>{spans.length} spans</span>
      </div>

      {/* CC-4: Document metadata panel */}
      {(doc.publisher_name || doc.source_reliability != null) && (
        <div className={styles.documentMeta}>
          {doc.publisher_name && (
            <div className={styles.metaRow}>
              <span className={styles.metaLabel}>Publisher:</span>
              <span>{doc.publisher_name}</span>
            </div>
          )}
          {doc.source_reliability != null && (() => {
            const reliability = formatReliability(doc.source_reliability);
            return reliability ? (
              <div className={styles.metaRow}>
                <span className={styles.metaLabel}>Reliability:</span>
                <span className={`${styles.reliabilityBadge} ${styles[reliability.className]}`}>
                  {reliability.label}
                </span>
                {doc.mbfc_factual_rating && (
                  <span className={styles.mbfcDetail}>
                    (MBFC: {doc.mbfc_factual_rating})
                  </span>
                )}
              </div>
            ) : null;
          })()}
          {doc.mbfc_bias_rating && (
            <div className={styles.metaRow}>
              <span className={styles.metaLabel}>Bias:</span>
              <span className={styles.biasBadge}>{doc.mbfc_bias_rating}</span>
            </div>
          )}
        </div>
      )}

      {/* SpanAnnotator */}
      <SpanAnnotator
        sourceText={doc.source_text}
        spans={spans}
        mode="edit"
        onCreate={handleCreate}
        onResize={handleResize}
        onDelete={handleDelete}
        onToggle={handleToggle}
        onAcceptPrefill={handleAcceptPrefill}
        spanQualityStates={spanQualityStates}
        onQualityChange={handleQualityChange}
      />

      {/* Document flags */}
      <div className={styles.flags}>
        <label className={styles.flagLabel}>
          <input
            type="checkbox"
            checked={exhaustivelyAnnotated}
            onChange={(e) => {
              setExhaustivelyAnnotated(e.target.checked);
              setHasUnsavedChanges(true);
            }}
          />
          <span>Exhaustively annotated</span>
        </label>
        <label className={styles.flagLabel}>
          <input
            type="checkbox"
            checked={lostEvidenceFlag}
            onChange={(e) => {
              setLostEvidenceFlag(e.target.checked);
              setHasUnsavedChanges(true);
            }}
          />
          <span>Lost evidence flag</span>
        </label>
        <Button
          size="sm"
          onClick={handleSaveFlags}
          disabled={!hasUnsavedChanges || updateDocumentMutation.isPending}
        >
          {updateDocumentMutation.isPending ? 'Saving...' : 'Save Flags'}
        </Button>
      </div>
    </div>
  );
}
