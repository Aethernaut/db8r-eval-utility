import { useParams } from 'react-router';
import styles from './T3StancePage.module.css';

export function T3StancePage() {
  const { claimId } = useParams();

  return (
    <div className={styles.page}>
      <h1 className={styles.title}>T3: Stance/Strength Labeling</h1>
      <p className={styles.subtitle}>Claim ID: {claimId}</p>
      <div className={styles.deferred}>
        <span className={styles.badge}>Coming in v2</span>
        <p>
          T3 stance/strength labeling is deferred until the v2 stance scoring and MC-2
          evidential_relation lands. This route is a placeholder.
        </p>
      </div>
    </div>
  );
}
