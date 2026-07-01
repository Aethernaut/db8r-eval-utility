import { type InputHTMLAttributes, forwardRef } from 'react';
import { cn } from '@/lib/utils';
import styles from './Input.module.css';

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  error?: boolean;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, error, ...props }, ref) => {
    return (
      <input
        ref={ref}
        className={cn(styles.input, error && styles.error, className)}
        {...props}
      />
    );
  },
);

Input.displayName = 'Input';
