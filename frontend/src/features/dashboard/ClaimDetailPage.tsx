import { useParams } from 'react-router';
import styles from './DashboardPage.module.css';

export function ClaimDetailPage() {
  const { claimId } = useParams();

  return (
    <div className={styles.page}>
      <h1 className={styles.title}>Claim: {claimId}</h1>
      <p className={styles.placeholder}>
        Claim details, status, and drill-in links will appear here.
      </p>
    </div>
  );
}
