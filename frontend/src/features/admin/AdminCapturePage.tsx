import { useState, useCallback } from 'react';
import { useAuth } from '@/features/auth/AuthProvider';
import { Navigate } from 'react-router';
import { useMutation } from '@tanstack/react-query';
import { apiPost } from '@/api/client';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import styles from './AdminPage.module.css';

type CaptureMode = 'search' | 'extract' | 'foraging';

interface CaptureJobResponse {
  fixture_id: string;
  status: string;
}

export function AdminCapturePage() {
  const { isAdmin } = useAuth();

  const [mode, setMode] = useState<CaptureMode>('search');
  const [query, setQuery] = useState('');
  const [claimText, setClaimText] = useState('');
  const [lastJob, setLastJob] = useState<CaptureJobResponse | null>(null);

  if (!isAdmin) {
    return <Navigate to="/" replace />;
  }

  const captureMutation = useMutation({
    mutationFn: async (data: { mode: CaptureMode; query?: string; claim_text?: string }) => {
      let endpoint = '/api/v1/capture/';
      let payload: Record<string, unknown> = {};

      if (data.mode === 'search') {
        endpoint += 'search';
        payload = { query: data.query };
      } else if (data.mode === 'extract') {
        endpoint += 'extract';
        payload = { query: data.query };
      } else if (data.mode === 'foraging') {
        endpoint += 'foraging';
        payload = { claim_text: data.claim_text };
      }

      return apiPost<CaptureJobResponse>(endpoint, payload);
    },
    onSuccess: (data) => {
      setLastJob(data);
      setQuery('');
      setClaimText('');
    },
  });

  const handleCapture = useCallback(() => {
    if (mode === 'foraging') {
      if (!claimText) return;
      captureMutation.mutate({ mode, claim_text: claimText });
    } else {
      if (!query) return;
      captureMutation.mutate({ mode, query });
    }
  }, [mode, query, claimText, captureMutation]);

  return (
    <div className={styles.page}>
      <h1 className={styles.title}>Capture Jobs</h1>

      <div className={styles.captureForm}>
        <div className={styles.field}>
          <label className={styles.label}>Capture Mode</label>
          <div className={styles.radioGroup}>
            <label className={styles.radioLabel}>
              <input
                type="radio"
                name="mode"
                value="search"
                checked={mode === 'search'}
                onChange={() => setMode('search')}
              />
              <span>Mode A: Search</span>
            </label>
            <label className={styles.radioLabel}>
              <input
                type="radio"
                name="mode"
                value="extract"
                checked={mode === 'extract'}
                onChange={() => setMode('extract')}
              />
              <span>Mode B: Extract</span>
            </label>
            <label className={styles.radioLabel}>
              <input
                type="radio"
                name="mode"
                value="foraging"
                checked={mode === 'foraging'}
                onChange={() => setMode('foraging')}
              />
              <span>Foraging</span>
            </label>
          </div>
        </div>

        {mode === 'foraging' ? (
          <div className={styles.field}>
            <label className={styles.label}>Claim Text</label>
            <textarea
              className={styles.textarea}
              value={claimText}
              onChange={(e) => setClaimText(e.target.value)}
              placeholder="Enter the claim to generate foraging queries for..."
              rows={3}
            />
          </div>
        ) : (
          <div className={styles.field}>
            <label className={styles.label}>Query</label>
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={mode === 'search' ? 'Search query...' : 'Query/claim to extract...'}
            />
          </div>
        )}

        <Button
          onClick={handleCapture}
          disabled={
            captureMutation.isPending ||
            (mode === 'foraging' ? !claimText : !query)
          }
        >
          {captureMutation.isPending ? 'Running...' : 'Run Capture'}
        </Button>
      </div>

      {captureMutation.error && (
        <div className={styles.error}>
          Capture failed. Please check the backend logs.
        </div>
      )}

      {lastJob && (
        <div className={styles.successBox}>
          <h3>Capture Complete</h3>
          <p>Fixture ID: <code>{lastJob.fixture_id}</code></p>
          <p>Status: {lastJob.status}</p>
        </div>
      )}

      <div className={styles.infoBox}>
        <h3>Capture Modes</h3>
        <dl>
          <dt>Mode A: Search</dt>
          <dd>Runs ClaimCheck unilateral search. Captures retrieval results for measuring retrieval metrics.</dd>

          <dt>Mode B: Extract</dt>
          <dd>Runs ClaimCheck extraction. Captures spans independent of retrieval for extraction metrics.</dd>

          <dt>Foraging</dt>
          <dd>Runs db8r-mcts foraging strategy generation. Captures query portfolio for foraging recall.</dd>
        </dl>
      </div>
    </div>
  );
}
