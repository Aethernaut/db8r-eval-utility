import { Routes, Route, Navigate } from 'react-router';
import { useAuth } from './features/auth/AuthProvider';
import { ProtectedRoute } from './features/auth/ProtectedRoute';
import { AppShell } from './components/layout/AppShell';
import { LoginPage } from './features/auth/LoginPage';
import { AcceptInvitePage } from './features/auth/AcceptInvitePage';
import { DashboardPage } from './features/dashboard/DashboardPage';
import { T1RetrievalPage } from './features/t1-retrieval/T1RetrievalPage';
import { T2SpanPage } from './features/t2-span/T2SpanPage';
import { T3StancePage } from './features/t3-stance/T3StancePage';
import { ClaimDetailPage } from './features/dashboard/ClaimDetailPage';
import { ReportPage } from './features/report/ReportPage';
import { AdminUsersPage } from './features/admin/AdminUsersPage';
import { AdminCapturePage } from './features/admin/AdminCapturePage';
import { LoadingSpinner } from './components/ui/LoadingSpinner';

export function App() {
  const { isLoading } = useAuth();

  if (isLoading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh' }}>
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  return (
    <Routes>
      {/* Public routes */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/accept-invite" element={<AcceptInvitePage />} />

      {/* Protected routes */}
      <Route element={<ProtectedRoute />}>
        <Route element={<AppShell />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/queue/t1" element={<Navigate to="/t1/next" replace />} />
          <Route path="/queue/t2" element={<Navigate to="/t2/next" replace />} />
          <Route path="/claims/:claimId" element={<ClaimDetailPage />} />
          <Route path="/t1/:claimId" element={<T1RetrievalPage />} />
          <Route path="/t2/:documentId" element={<T2SpanPage />} />
          <Route path="/t3/:claimId" element={<T3StancePage />} />
          <Route path="/report" element={<ReportPage />} />

          {/* Admin routes */}
          <Route path="/admin/users" element={<AdminUsersPage />} />
          <Route path="/admin/capture" element={<AdminCapturePage />} />
        </Route>
      </Route>

      {/* Fallback */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
