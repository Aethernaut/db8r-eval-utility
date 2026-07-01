import { cn } from '@/lib/utils';
import styles from './LoadingSpinner.module.css';

interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export function LoadingSpinner({ size = 'md', className }: LoadingSpinnerProps) {
  return (
    <div className={cn(styles.spinner, styles[size], className)} role="status">
      <span className="sr-only">Loading...</span>
    </div>
  );
}
