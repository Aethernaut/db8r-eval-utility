import { useState, useCallback } from 'react';
import { useAuth } from '@/features/auth/AuthProvider';
import { Navigate } from 'react-router';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiGet, apiPost, apiPut } from '@/api/client';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import styles from './AdminPage.module.css';

interface UserResponse {
  user_id: string;
  email: string;
  role: string;
  disabled: boolean;
  created_at: string;
}

interface UsersListResponse {
  users: UserResponse[];
  total: number;
}

interface InviteResponse {
  email: string;
  role: string;
  token: string;
  invite_url: string;
  expires_at: string;
}

export function AdminUsersPage() {
  const { isAdmin } = useAuth();
  const queryClient = useQueryClient();

  const [showInviteDialog, setShowInviteDialog] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState<'admin' | 'annotator'>('annotator');
  const [inviteUrl, setInviteUrl] = useState<string | null>(null);

  if (!isAdmin) {
    return <Navigate to="/" replace />;
  }

  const usersQuery = useQuery({
    queryKey: ['admin-users'],
    queryFn: () => apiGet<UsersListResponse>('/api/v1/users'),
  });

  const inviteMutation = useMutation({
    mutationFn: (data: { email: string; role: string }) =>
      apiPost<InviteResponse>('/api/v1/users/invite', data),
    onSuccess: (data) => {
      setInviteUrl(data.invite_url);
      queryClient.invalidateQueries({ queryKey: ['admin-users'] });
    },
  });

  const toggleDisableMutation = useMutation({
    mutationFn: ({ userId, disabled }: { userId: string; disabled: boolean }) =>
      apiPut<UserResponse>(`/api/v1/users/${userId}`, { disabled }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] });
    },
  });

  const handleInvite = useCallback(() => {
    if (!inviteEmail) return;
    inviteMutation.mutate({ email: inviteEmail, role: inviteRole });
  }, [inviteEmail, inviteRole, inviteMutation]);

  const handleCloseInviteDialog = useCallback(() => {
    setShowInviteDialog(false);
    setInviteEmail('');
    setInviteRole('annotator');
    setInviteUrl(null);
  }, []);

  const handleToggleDisable = useCallback(
    (userId: string, currentDisabled: boolean) => {
      toggleDisableMutation.mutate({ userId, disabled: !currentDisabled });
    },
    [toggleDisableMutation],
  );

  if (usersQuery.isLoading) {
    return (
      <div className={styles.loading}>
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  const users = usersQuery.data?.users ?? [];

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1 className={styles.title}>User Management</h1>
        <Button onClick={() => setShowInviteDialog(true)}>Invite User</Button>
      </div>

      {/* Users Table */}
      <div className={styles.tableContainer}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Email</th>
              <th>Role</th>
              <th>Status</th>
              <th>Created</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) => (
              <tr key={user.user_id}>
                <td>{user.email}</td>
                <td>
                  <span className={`${styles.badge} ${styles[user.role]}`}>
                    {user.role}
                  </span>
                </td>
                <td>
                  <span
                    className={`${styles.badge} ${user.disabled ? styles.disabled : styles.active}`}
                  >
                    {user.disabled ? 'Disabled' : 'Active'}
                  </span>
                </td>
                <td>{new Date(user.created_at).toLocaleDateString()}</td>
                <td>
                  <Button
                    variant={user.disabled ? 'secondary' : 'danger'}
                    size="sm"
                    onClick={() => handleToggleDisable(user.user_id, user.disabled)}
                  >
                    {user.disabled ? 'Enable' : 'Disable'}
                  </Button>
                </td>
              </tr>
            ))}
            {users.length === 0 && (
              <tr>
                <td colSpan={5} className={styles.empty}>
                  No users yet
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Invite Dialog */}
      {showInviteDialog && (
        <div className={styles.overlay} onClick={handleCloseInviteDialog}>
          <div className={styles.dialog} onClick={(e) => e.stopPropagation()}>
            <h2 className={styles.dialogTitle}>Invite User</h2>

            {inviteUrl ? (
              <div className={styles.inviteSuccess}>
                <p>Invite created! Share this link with the user:</p>
                <div className={styles.inviteUrlBox}>
                  <code>{inviteUrl}</code>
                </div>
                <Button onClick={handleCloseInviteDialog}>Done</Button>
              </div>
            ) : (
              <>
                <div className={styles.field}>
                  <label className={styles.label}>Email</label>
                  <Input
                    type="email"
                    value={inviteEmail}
                    onChange={(e) => setInviteEmail(e.target.value)}
                    placeholder="user@example.com"
                    autoFocus
                  />
                </div>

                <div className={styles.field}>
                  <label className={styles.label}>Role</label>
                  <div className={styles.radioGroup}>
                    <label className={styles.radioLabel}>
                      <input
                        type="radio"
                        name="role"
                        value="annotator"
                        checked={inviteRole === 'annotator'}
                        onChange={() => setInviteRole('annotator')}
                      />
                      <span>Annotator</span>
                    </label>
                    <label className={styles.radioLabel}>
                      <input
                        type="radio"
                        name="role"
                        value="admin"
                        checked={inviteRole === 'admin'}
                        onChange={() => setInviteRole('admin')}
                      />
                      <span>Admin</span>
                    </label>
                  </div>
                </div>

                <div className={styles.dialogActions}>
                  <Button variant="secondary" onClick={handleCloseInviteDialog}>
                    Cancel
                  </Button>
                  <Button
                    onClick={handleInvite}
                    disabled={!inviteEmail || inviteMutation.isPending}
                  >
                    {inviteMutation.isPending ? 'Creating...' : 'Create Invite'}
                  </Button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
