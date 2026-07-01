import { useQuery } from '@tanstack/react-query';
import { apiGet } from '@/api/client';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { Link } from 'react-router';
import styles from './DashboardPage.module.css';

interface DatasetResponse {
  dataset_version: string;
  schema_version: string;
  annotation_guidelines_version: string | null;
  created_at: string;
  updated_at: string;
  record_counts: Record<string, number>;
}

interface ClaimResponse {
  claim_id: string;
  text: string;
  family: string | null;
  split: string;
}

interface ClaimListResponse {
  claims: ClaimResponse[];
  total: number;
}

export function DashboardPage() {
  const datasetQuery = useQuery({
    queryKey: ['dataset'],
    queryFn: () => apiGet<DatasetResponse>('/api/v1/dataset'),
  });

  const claimsQuery = useQuery({
    queryKey: ['claims'],
    queryFn: () => apiGet<ClaimListResponse>('/api/v1/claims?limit=100'),
  });

  if (datasetQuery.isLoading || claimsQuery.isLoading) {
    return (
      <div className={styles.loading}>
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  const dataset = datasetQuery.data;
  const claims = claimsQuery.data?.claims ?? [];

  // Compute claim stats
  const claimsByFamily = claims.reduce((acc, c) => {
    const family = c.family ?? 'unclassified';
    acc[family] = (acc[family] ?? 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  const claimsBySplit = claims.reduce((acc, c) => {
    acc[c.split] = (acc[c.split] ?? 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  return (
    <div className={styles.page}>
      <h1 className={styles.title}>Dashboard</h1>

      <div className={styles.grid}>
        {/* Task Queue Cards */}
        <div className={styles.card}>
          <h2 className={styles.cardTitle}>T1: Retrieval Judgments</h2>
          <p className={styles.cardDescription}>
            Judge relevance of retrieved documents for each claim
          </p>
          <Link to="/queue/t1" className={styles.cardAction}>
            Start judging
          </Link>
        </div>

        <div className={styles.card}>
          <h2 className={styles.cardTitle}>T2: Span Annotation</h2>
          <p className={styles.cardDescription}>
            Annotate claim-bearing spans in source documents
          </p>
          <Link to="/queue/t2" className={styles.cardAction}>
            Start annotating
          </Link>
        </div>

        {/* Dataset Stats */}
        <div className={styles.card}>
          <h2 className={styles.cardTitle}>Dataset Status</h2>
          {dataset ? (
            <div className={styles.stats}>
              <div className={styles.stat}>
                <span className={styles.statLabel}>Version</span>
                <span className={styles.statValue}>{dataset.dataset_version}</span>
              </div>
              <div className={styles.stat}>
                <span className={styles.statLabel}>Claims</span>
                <span className={styles.statValue}>{dataset.record_counts.claims ?? 0}</span>
              </div>
              <div className={styles.stat}>
                <span className={styles.statLabel}>Gold Spans</span>
                <span className={styles.statValue}>{dataset.record_counts.gold_spans ?? 0}</span>
              </div>
              <div className={styles.stat}>
                <span className={styles.statLabel}>Judgments</span>
                <span className={styles.statValue}>{dataset.record_counts.retrieval_judgments ?? 0}</span>
              </div>
            </div>
          ) : (
            <p className={styles.empty}>No dataset loaded</p>
          )}
        </div>

        {/* Claims by Family */}
        <div className={styles.card}>
          <h2 className={styles.cardTitle}>Claims by Family</h2>
          <div className={styles.stats}>
            {Object.entries(claimsByFamily).map(([family, count]) => (
              <div key={family} className={styles.stat}>
                <span className={styles.statLabel}>{family}</span>
                <span className={styles.statValue}>{count}</span>
              </div>
            ))}
            {Object.keys(claimsByFamily).length === 0 && (
              <p className={styles.empty}>No claims yet</p>
            )}
          </div>
        </div>

        {/* Claims by Split */}
        <div className={styles.card}>
          <h2 className={styles.cardTitle}>Claims by Split</h2>
          <div className={styles.stats}>
            {Object.entries(claimsBySplit).map(([split, count]) => (
              <div key={split} className={styles.stat}>
                <span className={styles.statLabel}>{split}</span>
                <span className={styles.statValue}>{count}</span>
              </div>
            ))}
            {Object.keys(claimsBySplit).length === 0 && (
              <p className={styles.empty}>No claims yet</p>
            )}
          </div>
        </div>

        {/* Report Link */}
        <div className={styles.card}>
          <h2 className={styles.cardTitle}>Scorer Report</h2>
          <p className={styles.cardDescription}>
            View evaluation metrics and analysis
          </p>
          <Link to="/report" className={styles.cardAction}>
            View report
          </Link>
        </div>
      </div>
    </div>
  );
}
