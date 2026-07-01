import { NavLink } from 'react-router';
import { useAuth } from '@/features/auth/AuthProvider';
import { cn } from '@/lib/utils';
import styles from './Sidebar.module.css';

interface NavItem {
  to: string;
  label: string;
  adminOnly?: boolean;
}

const navItems: NavItem[] = [
  { to: '/', label: 'Dashboard' },
  { to: '/queue/t1', label: 'T1: Retrieval' },
  { to: '/queue/t2', label: 'T2: Spans' },
  { to: '/report', label: 'Report' },
];

const adminItems: NavItem[] = [
  { to: '/admin/users', label: 'Users', adminOnly: true },
  { to: '/admin/capture', label: 'Capture', adminOnly: true },
];

export function Sidebar() {
  const { isAdmin } = useAuth();

  return (
    <aside className={styles.sidebar}>
      <div className={styles.logo}>
        <span className={styles.logoText}>DB8R Eval</span>
      </div>

      <nav className={styles.nav}>
        <div className={styles.section}>
          <span className={styles.sectionTitle}>Annotation</span>
          <ul className={styles.navList}>
            {navItems.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  className={({ isActive }) =>
                    cn(styles.navLink, isActive && styles.active)
                  }
                  end={item.to === '/'}
                >
                  {item.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </div>

        {isAdmin && (
          <div className={styles.section}>
            <span className={styles.sectionTitle}>Admin</span>
            <ul className={styles.navList}>
              {adminItems.map((item) => (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    className={({ isActive }) =>
                      cn(styles.navLink, isActive && styles.active)
                    }
                  >
                    {item.label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        )}
      </nav>
    </aside>
  );
}
