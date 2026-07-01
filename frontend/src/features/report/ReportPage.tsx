import { useQuery } from '@tanstack/react-query';
import { apiGet } from '@/api/client';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import styles from './ReportPage.module.css';

interface ScorerReport {
  generated_at: string;
  retrieval: {
    recall_at_k: Record<string, number>;
    precision_at_k: Record<string, number>;
    claim_coverage: number;
    primary_source_coverage: number;
  };
  extraction: {
    well_formedness_precision: number;
    targeting_precision: number;
    germane_recall: number;
    well_formed_recall: number;
    f1_germane: number;
  };
  fidelity: {
    match_method_distribution: Record<string, number>;
    mean_extraction_fidelity: number;
    verbatim_locatability_rate: number;
  };
  coverage: {
    lost_evidence_rate: number;
  };
}

export function ReportPage() {
  const reportQuery = useQuery({
    queryKey: ['scorer-report'],
    queryFn: () => apiGet<ScorerReport>('/api/v1/report'),
  });

  if (reportQuery.isLoading) {
    return (
      <div className={styles.loading}>
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (reportQuery.error || !reportQuery.data) {
    return (
      <div className={styles.page}>
        <h1 className={styles.title}>Scorer Report</h1>
        <div className={styles.placeholder}>
          <p>No scorer report available yet.</p>
          <p className={styles.hint}>
            Run the scorer to generate a report with retrieval, extraction, fidelity, and coverage metrics.
          </p>
        </div>
      </div>
    );
  }

  const report = reportQuery.data;

  const formatPercent = (value: number) => `${(value * 100).toFixed(1)}%`;
  const formatDecimal = (value: number) => value.toFixed(3);

  return (
    <div className={styles.page}>
      <h1 className={styles.title}>Scorer Report</h1>
      <p className={styles.generated}>Generated: {new Date(report.generated_at).toLocaleString()}</p>

      <div className={styles.grid}>
        {/* Retrieval Metrics */}
        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>Retrieval</h2>
          <div className={styles.metricsGrid}>
            <div className={styles.metric}>
              <span className={styles.metricLabel}>Claim Coverage</span>
              <span className={styles.metricValue}>{formatPercent(report.retrieval.claim_coverage)}</span>
            </div>
            <div className={styles.metric}>
              <span className={styles.metricLabel}>Primary Source Coverage</span>
              <span className={styles.metricValue}>{formatPercent(report.retrieval.primary_source_coverage)}</span>
            </div>
          </div>

          <h3 className={styles.subTitle}>Recall@k</h3>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>k</th>
                <th>Recall</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(report.retrieval.recall_at_k).map(([k, value]) => (
                <tr key={k}>
                  <td>{k}</td>
                  <td>{formatPercent(value)}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <h3 className={styles.subTitle}>Precision@k</h3>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>k</th>
                <th>Precision</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(report.retrieval.precision_at_k).map(([k, value]) => (
                <tr key={k}>
                  <td>{k}</td>
                  <td>{formatPercent(value)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        {/* Extraction Metrics */}
        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>Extraction</h2>
          <div className={styles.metricsGrid}>
            <div className={styles.metric}>
              <span className={styles.metricLabel}>Well-formedness Precision</span>
              <span className={styles.metricValue}>{formatPercent(report.extraction.well_formedness_precision)}</span>
            </div>
            <div className={styles.metric}>
              <span className={styles.metricLabel}>Targeting Precision</span>
              <span className={styles.metricValue}>{formatPercent(report.extraction.targeting_precision)}</span>
            </div>
            <div className={styles.metric}>
              <span className={styles.metricLabel}>Germane Recall</span>
              <span className={styles.metricValue}>{formatPercent(report.extraction.germane_recall)}</span>
            </div>
            <div className={styles.metric}>
              <span className={styles.metricLabel}>Well-formed Recall</span>
              <span className={styles.metricValue}>{formatPercent(report.extraction.well_formed_recall)}</span>
            </div>
            <div className={styles.metric + ' ' + styles.highlight}>
              <span className={styles.metricLabel}>F1 Germane</span>
              <span className={styles.metricValue}>{formatPercent(report.extraction.f1_germane)}</span>
            </div>
          </div>
        </section>

        {/* Fidelity Metrics */}
        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>Fidelity</h2>
          <div className={styles.metricsGrid}>
            <div className={styles.metric}>
              <span className={styles.metricLabel}>Mean Extraction Fidelity</span>
              <span className={styles.metricValue}>{formatDecimal(report.fidelity.mean_extraction_fidelity)}</span>
            </div>
            <div className={styles.metric}>
              <span className={styles.metricLabel}>Verbatim Locatability</span>
              <span className={styles.metricValue}>{formatPercent(report.fidelity.verbatim_locatability_rate)}</span>
            </div>
          </div>

          <h3 className={styles.subTitle}>Match Method Distribution</h3>
          <div className={styles.distribution}>
            {Object.entries(report.fidelity.match_method_distribution).map(([method, value]) => (
              <div key={method} className={styles.distributionItem}>
                <span className={styles.distributionLabel}>{method}</span>
                <div className={styles.distributionBar}>
                  <div
                    className={styles.distributionFill}
                    style={{ width: `${value * 100}%` }}
                  />
                </div>
                <span className={styles.distributionValue}>{formatPercent(value)}</span>
              </div>
            ))}
          </div>
        </section>

        {/* Coverage Metrics */}
        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>Coverage</h2>
          <div className={styles.metricsGrid}>
            <div className={styles.metric}>
              <span className={styles.metricLabel}>Lost Evidence Rate</span>
              <span className={styles.metricValue}>{formatPercent(report.coverage.lost_evidence_rate)}</span>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
