import { useAuth } from '@/features/auth/AuthProvider';
import { Button } from '@/components/ui/Button';
import styles from './Header.module.css';

export function Header() {
  const { user, logout } = useAuth();

  return (
    <header className={styles.header}>
      <div className={styles.spacer} />
      <div className={styles.userSection}>
        <span className={styles.email}>{user?.email}</span>
        <span className={styles.role}>{user?.role}</span>
        <Button variant="ghost" size="sm" onClick={logout}>
          Sign out
        </Button>
      </div>
    </header>
  );
}
