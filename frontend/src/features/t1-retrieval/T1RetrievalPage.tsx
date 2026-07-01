import { useState, useCallback, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiGet, apiPost, apiPut } from '@/api/client';
import { Button } from '@/components/ui/Button';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { DocumentQualityPanel, type DocumentQualityState } from '@/components/QualityLabels';
import type { DocumentQualityLabel } from '@/types/qualityLabels';
import styles from './T1RetrievalPage.module.css';

interface ClaimResponse {
  claim_id: string;
  text: string;
  family: string | null;
  proof_standard: string | null;
  split: string;
  notes: string | null;
}

interface FixtureDocumentResponse {
  document_id: string;
  source_url: string;
  source_title: string | null;
  source_text_hash: string;
  source_text_char_len: number;
  retrieval_rank: number | null;
  source_reliability: number | null;
  // CC-4: MBFC Source Reliability metadata
  publisher_name: string | null;
  publisher_mbfc_key: string | null;
  mbfc_factual_rating: string | null;
  mbfc_bias_rating: string | null;
}

// CC-4: Helper function to format reliability score as badge
function formatReliability(score: number | null | undefined): { label: string; className: string } | null {
  if (score == null) return null;
  if (score >= 0.8) return { label: 'High', className: 'reliabilityHigh' };
  if (score >= 0.6) return { label: 'Medium', className: 'reliabilityMedium' };
  return { label: 'Low', className: 'reliabilityLow' };
}

interface ClaimDocumentLinkResponse {
  claim_id: string;
  document_id: string;
  origin: string;
  fixture_id: string | null;
}

interface RetrievalJudgmentResponse {
  claim_id: string;
  document_id: string;
  relevant: number | null;
  notes: string | null;
}

interface JudgmentBatchResponse {
  created_count: number;
  updated_count: number;
  judgments: RetrievalJudgmentResponse[];
}

// Relevance scale: 0 = not relevant, 1 = marginally, 2 = relevant, 3 = highly relevant
const RELEVANCE_OPTIONS = [
  { value: 0, label: 'Not Relevant', description: 'Document has no bearing on the claim' },
  { value: 1, label: 'Marginally', description: 'Tangentially related or very weak evidence' },
  { value: 2, label: 'Relevant', description: 'Contains evidence that addresses the claim' },
  { value: 3, label: 'Highly Relevant', description: 'Strong, direct evidence for/against the claim' },
];

interface DocumentJudgment {
  documentId: string;
  relevant: number | null;
  notes: string;
}

interface DocumentQualityLabelResponse {
  id: string;
  document_id: string;
  claim_id: string | null;
  relevance: string | null;
  claim_relation: string | null;
  source_issues: string[] | null;
  corroboration_status: string | null;
  corroboration_cluster_id: string | null;
}

interface DocumentQualityLabelListResponse {
  labels: DocumentQualityLabelResponse[];
  total: number;
}

export function T1RetrievalPage() {
  const { claimId: rawClaimId } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [judgments, setJudgments] = useState<Map<string, DocumentJudgment>>(new Map());
  const [qualityLabels, setQualityLabels] = useState<Map<string, DocumentQualityState>>(new Map());
  const [hasChanges, setHasChanges] = useState(false);
  const [expandedDocs, setExpandedDocs] = useState<Set<string>>(new Set());

  // Handle "next" special case - fetch next incomplete claim and redirect
  const nextClaimQuery = useQuery({
    queryKey: ['next-claim'],
    queryFn: () => apiGet<ClaimResponse>('/api/v1/claims/next'),
    enabled: rawClaimId === 'next',
    retry: false,
  });

  // Redirect to actual claim ID when "next" resolves
  useEffect(() => {
    if (rawClaimId === 'next' && nextClaimQuery.data) {
      navigate(`/t1/${nextClaimQuery.data.claim_id}`, { replace: true });
    }
  }, [rawClaimId, nextClaimQuery.data, navigate]);

  // Use the actual claim ID (not "next")
  const claimId = rawClaimId === 'next' ? undefined : rawClaimId;

  // Fetch claim
  const claimQuery = useQuery({
    queryKey: ['claim', claimId],
    queryFn: () => apiGet<ClaimResponse>(`/api/v1/claims/${claimId}`),
    enabled: !!claimId && claimId !== 'next',
  });

  // Fetch documents linked to this claim
  const linksQuery = useQuery({
    queryKey: ['claim-documents', claimId],
    queryFn: () =>
      apiGet<ClaimDocumentLinkResponse[]>(
        `/api/v1/claims/${claimId}/documents`,
      ),
    enabled: !!claimId && claimId !== 'next',
  });

  // Fetch existing judgments for this claim
  const judgmentsQuery = useQuery({
    queryKey: ['judgments', claimId],
    queryFn: () =>
      apiGet<{ judgments: RetrievalJudgmentResponse[] }>(
        `/api/v1/judgments?claim_id=${claimId}&limit=100`,
      ),
    enabled: !!claimId && claimId !== 'next',
  });

  // Fetch document details for each linked document
  const documents = linksQuery.data ?? [];
  const documentDetailsQueries = useQuery({
    queryKey: ['document-details', documents.map((d) => d.document_id)],
    queryFn: async () => {
      const details: Map<string, FixtureDocumentResponse> = new Map();
      for (const link of documents) {
        if (!link.fixture_id) continue;
        try {
          const doc = await apiGet<FixtureDocumentResponse>(
            `/api/v1/fixtures/${link.fixture_id}/documents/${link.document_id}`,
          );
          details.set(link.document_id, doc);
        } catch {
          // Skip failed fetches
        }
      }
      return details;
    },
    enabled: documents.length > 0,
  });

  // Fetch existing quality labels for this claim's documents
  const qualityLabelsQuery = useQuery({
    queryKey: ['quality-labels', claimId],
    queryFn: () =>
      apiGet<DocumentQualityLabelListResponse>(
        `/api/v1/quality-labels/documents?claim_id=${claimId}&limit=100`,
      ),
    enabled: !!claimId && claimId !== 'next',
  });

  // Initialize judgments from existing data
  useEffect(() => {
    if (judgmentsQuery.data?.judgments) {
      const initial = new Map<string, DocumentJudgment>();
      for (const j of judgmentsQuery.data.judgments) {
        initial.set(j.document_id, {
          documentId: j.document_id,
          relevant: j.relevant,
          notes: j.notes ?? '',
        });
      }
      setJudgments(initial);
    }
  }, [judgmentsQuery.data]);

  // Initialize quality labels from existing data
  useEffect(() => {
    if (qualityLabelsQuery.data?.labels) {
      const initial = new Map<string, DocumentQualityState>();
      for (const label of qualityLabelsQuery.data.labels) {
        initial.set(label.document_id, {
          relevance: label.relevance as DocumentQualityState['relevance'],
          claimRelation: label.claim_relation as DocumentQualityState['claimRelation'],
          sourceIssues: (label.source_issues ?? []) as DocumentQualityState['sourceIssues'],
          corroborationStatus: label.corroboration_status as DocumentQualityState['corroborationStatus'],
        });
      }
      setQualityLabels(initial);
    }
  }, [qualityLabelsQuery.data]);

  // Batch save mutation
  const batchSaveMutation = useMutation({
    mutationFn: (data: { judgments: Array<{ claim_id: string; document_id: string; relevant: number | null }> }) =>
      apiPost<JudgmentBatchResponse>('/api/v1/judgments/batch', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['judgments', claimId] });
      setHasChanges(false);
    },
  });

  // Mark claim complete mutation
  const markCompleteMutation = useMutation({
    mutationFn: () =>
      apiPut<ClaimResponse>(`/api/v1/claims/${claimId}`, { retrieval_complete: true }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['claim', claimId] });
      navigate('/');
    },
  });

  // Save quality label mutation
  const saveQualityLabelMutation = useMutation({
    mutationFn: (data: {
      document_id: string;
      claim_id: string;
      relevance: string | null;
      claim_relation: string | null;
      source_issues: string[] | null;
      corroboration_status: string | null;
    }) => apiPost<DocumentQualityLabel>('/api/v1/quality-labels/documents', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['quality-labels', claimId] });
    },
  });

  const handleRelevanceChange = useCallback((documentId: string, relevant: number) => {
    setJudgments((prev) => {
      const next = new Map(prev);
      const existing = next.get(documentId) ?? { documentId, relevant: null, notes: '' };
      next.set(documentId, { ...existing, relevant });
      return next;
    });
    setHasChanges(true);
  }, []);

  const handleQualityLabelChange = useCallback((documentId: string, state: DocumentQualityState) => {
    setQualityLabels((prev) => {
      const next = new Map(prev);
      next.set(documentId, state);
      return next;
    });
    setHasChanges(true);
  }, []);

  const toggleDocExpanded = useCallback((documentId: string) => {
    setExpandedDocs((prev) => {
      const next = new Set(prev);
      if (next.has(documentId)) {
        next.delete(documentId);
      } else {
        next.add(documentId);
      }
      return next;
    });
  }, []);

  const handleSave = useCallback(() => {
    // Save judgments
    const judgementsArray = Array.from(judgments.values())
      .filter((j) => j.relevant !== null)
      .map((j) => ({
        claim_id: claimId ?? '',
        document_id: j.documentId,
        relevant: j.relevant,
      }));

    batchSaveMutation.mutate({ judgments: judgementsArray });

    // Save quality labels
    for (const [documentId, state] of qualityLabels.entries()) {
      // Only save if at least one field is set
      if (state.relevance || state.claimRelation || state.sourceIssues.length > 0 || state.corroborationStatus) {
        saveQualityLabelMutation.mutate({
          document_id: documentId,
          claim_id: claimId ?? '',
          relevance: state.relevance,
          claim_relation: state.claimRelation,
          source_issues: state.sourceIssues.length > 0 ? state.sourceIssues : null,
          corroboration_status: state.corroborationStatus,
        });
      }
    }
  }, [claimId, judgments, qualityLabels, batchSaveMutation, saveQualityLabelMutation]);

  const handleComplete = useCallback(() => {
    // Save first, then mark complete
    handleSave();
    markCompleteMutation.mutate();
  }, [handleSave, markCompleteMutation]);

  // Loading state: either waiting for "next" redirect or loading claim data
  if (rawClaimId === 'next' && nextClaimQuery.isLoading) {
    return (
      <div className={styles.loading}>
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  // Error state: no incomplete claims found
  if (rawClaimId === 'next' && nextClaimQuery.error) {
    return (
      <div className={styles.error}>
        <h2>No claims to review</h2>
        <p>All claims have been marked as complete.</p>
        <Button onClick={() => navigate('/')}>Return to Dashboard</Button>
      </div>
    );
  }

  // Still waiting for redirect when claimId is "next"
  if (rawClaimId === 'next') {
    return (
      <div className={styles.loading}>
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (claimQuery.isLoading || linksQuery.isLoading) {
    return (
      <div className={styles.loading}>
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (claimQuery.error || !claimQuery.data) {
    return (
      <div className={styles.error}>
        <h2>Claim not found</h2>
        <p>Could not load claim with ID: {claimId}</p>
        <Button onClick={() => navigate('/')}>Return to Dashboard</Button>
      </div>
    );
  }

  const claim = claimQuery.data;
  const documentDetails = documentDetailsQueries.data ?? new Map();

  return (
    <div className={styles.page}>
      {/* Claim Header */}
      <div className={styles.claimCard}>
        <div className={styles.claimHeader}>
          <span className={styles.claimBadge}>{claim.family ?? 'uncategorized'}</span>
          <span className={styles.claimBadge}>{claim.split}</span>
          {claim.proof_standard && (
            <span className={styles.claimBadge}>{claim.proof_standard}</span>
          )}
        </div>
        <p className={styles.claimText}>{claim.text}</p>
      </div>

      {/* Instructions */}
      <div className={styles.instructions}>
        <strong>Task:</strong> Rate each document's relevance to the claim above.
        Consider whether the document contains evidence that could support or refute the claim.
      </div>

      {/* Document List */}
      <div className={styles.documentList}>
        {documents.length === 0 && (
          <p className={styles.empty}>No documents linked to this claim yet.</p>
        )}

        {documents.map((link) => {
          const doc = documentDetails.get(link.document_id);
          const judgment = judgments.get(link.document_id);

          const reliability = doc ? formatReliability(doc.source_reliability) : null;

          return (
            <div key={link.document_id} className={styles.documentCard}>
              <div className={styles.documentHeader}>
                <h3 className={styles.documentTitle}>{doc?.source_title ?? 'Untitled'}</h3>
                <div className={styles.documentBadges}>
                  {doc?.retrieval_rank != null && (
                    <span className={styles.rankBadge}>Rank #{doc.retrieval_rank}</span>
                  )}
                  {reliability && (
                    <span
                      className={`${styles.reliabilityBadge} ${styles[reliability.className]}`}
                      title={doc?.mbfc_factual_rating ? `MBFC: ${doc.mbfc_factual_rating}` : undefined}
                    >
                      {reliability.label}
                    </span>
                  )}
                </div>
              </div>
              {doc?.publisher_name && (
                <div className={styles.publisherName}>
                  <span className={styles.publisherLabel}>Publisher:</span> {doc.publisher_name}
                  {doc.mbfc_bias_rating && (
                    <span className={styles.biasTag}>{doc.mbfc_bias_rating}</span>
                  )}
                </div>
              )}
              {doc && (
                <a
                  href={doc.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={styles.documentUrl}
                >
                  {doc.source_url}
                </a>
              )}
              <div className={styles.relevanceSelector}>
                {RELEVANCE_OPTIONS.map((option) => (
                  <button
                    key={option.value}
                    className={`${styles.relevanceButton} ${
                      judgment?.relevant === option.value ? styles.selected : ''
                    }`}
                    onClick={() => handleRelevanceChange(link.document_id, option.value)}
                    title={option.description}
                  >
                    <span className={styles.relevanceValue}>{option.value}</span>
                    <span className={styles.relevanceLabel}>{option.label}</span>
                  </button>
                ))}
              </div>

              {/* Quality Labels Toggle */}
              <button
                type="button"
                className={styles.qualityToggle}
                onClick={() => toggleDocExpanded(link.document_id)}
              >
                {expandedDocs.has(link.document_id) ? 'Hide' : 'Show'} Quality Labels
              </button>

              {/* Document Quality Panel (collapsible) */}
              {expandedDocs.has(link.document_id) && (
                <DocumentQualityPanel
                  initialState={qualityLabels.get(link.document_id)}
                  onChange={(state) => handleQualityLabelChange(link.document_id, state)}
                />
              )}
            </div>
          );
        })}
      </div>

      {/* Actions */}
      <div className={styles.actions}>
        <Button
          variant="secondary"
          onClick={handleSave}
          disabled={!hasChanges || batchSaveMutation.isPending}
        >
          {batchSaveMutation.isPending ? 'Saving...' : 'Save Progress'}
        </Button>
        <Button
          onClick={handleComplete}
          disabled={markCompleteMutation.isPending}
        >
          {markCompleteMutation.isPending ? 'Completing...' : 'Complete & Next'}
        </Button>
      </div>
    </div>
  );
}
