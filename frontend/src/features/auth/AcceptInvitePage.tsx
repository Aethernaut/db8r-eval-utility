import { useState, type FormEvent } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router';
import { apiPost } from '@/api/client';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import styles from './LoginPage.module.css';

interface AcceptInviteResponse {
  user_id: string;
  email: string;
  role: string;
}

export function AcceptInvitePage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get('token') ?? '';

  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!token) {
      setError('Invalid invite link. Please check your email for the correct link.');
      return;
    }

    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    if (password.length < 8) {
      setError('Password must be at least 8 characters');
      return;
    }

    setIsSubmitting(true);

    try {
      await apiPost<AcceptInviteResponse>('/auth/accept-invite', {
        token,
        password,
      });
      setSuccess(true);
    } catch (err) {
      if (err instanceof Response) {
        if (err.status === 400) {
          const data = await err.json().catch(() => ({ detail: 'Invalid request' }));
          setError(data.detail ?? 'Invalid or expired invite link');
        } else {
          setError('Failed to create account. Please try again.');
        }
      } else {
        setError('Network error. Please check your connection.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  if (success) {
    return (
      <div className={styles.container}>
        <div className={styles.card}>
          <h1 className={styles.title}>Account Created</h1>
          <p className={styles.subtitle}>
            Your account has been set up successfully. You can now sign in.
          </p>
          <Button onClick={() => navigate('/login')} className={styles.submitButton}>
            Go to Login
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      <div className={styles.card}>
        <h1 className={styles.title}>Set Up Your Account</h1>
        <p className={styles.subtitle}>Choose a password to complete your account setup</p>

        <form onSubmit={handleSubmit} className={styles.form}>
          {error && <div className={styles.error}>{error}</div>}

          <div className={styles.field}>
            <label htmlFor="password" className={styles.label}>
              Password
            </label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="new-password"
              minLength={8}
              autoFocus
            />
          </div>

          <div className={styles.field}>
            <label htmlFor="confirmPassword" className={styles.label}>
              Confirm Password
            </label>
            <Input
              id="confirmPassword"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              autoComplete="new-password"
              minLength={8}
            />
          </div>

          <Button type="submit" disabled={isSubmitting} className={styles.submitButton}>
            {isSubmitting ? 'Creating account...' : 'Create Account'}
          </Button>
        </form>

        <p className={styles.inviteLink}>
          Already have an account? <Link to="/login">Sign in</Link>
        </p>
      </div>
    </div>
  );
}
