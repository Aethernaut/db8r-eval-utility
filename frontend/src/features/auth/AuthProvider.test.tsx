import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router';
import { AuthProvider, useAuth } from './AuthProvider';

// Mock fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

// Test component that uses the auth context
function TestConsumer() {
  const { user, isLoading, isAuthenticated, login, logout } = useAuth();

  if (isLoading) {
    return <div>Loading...</div>;
  }

  if (!isAuthenticated) {
    return (
      <div>
        <span>Not authenticated</span>
        <button onClick={() => login('test@example.com', 'password123')}>
          Login
        </button>
      </div>
    );
  }

  return (
    <div>
      <span>User: {user?.email}</span>
      <span>Role: {user?.role}</span>
      <button onClick={logout}>Logout</button>
    </div>
  );
}

function renderWithProviders() {
  return render(
    <BrowserRouter>
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    </BrowserRouter>,
  );
}

describe('AuthProvider', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
  });

  it('shows loading state initially', () => {
    // Mock the /auth/me request to hang
    mockFetch.mockImplementation(() => new Promise(() => {}));

    renderWithProviders();

    expect(screen.getByText('Loading...')).toBeInTheDocument();
  });

  it('shows not authenticated when /auth/me fails', async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 401,
    });

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText('Not authenticated')).toBeInTheDocument();
    });
  });

  it('shows authenticated user when /auth/me succeeds', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      headers: { get: () => 'application/json' },
      json: () =>
        Promise.resolve({
          user_id: 'user-1',
          email: 'test@example.com',
          role: 'annotator',
        }),
    });

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText('User: test@example.com')).toBeInTheDocument();
      expect(screen.getByText('Role: annotator')).toBeInTheDocument();
    });
  });

  it('handles login successfully', async () => {
    const user = userEvent.setup();

    // First call: /auth/me fails (not logged in)
    // Second call: /auth/login succeeds
    mockFetch
      .mockResolvedValueOnce({
        ok: false,
        status: 401,
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: () =>
          Promise.resolve({
            user_id: 'user-1',
            email: 'test@example.com',
            role: 'annotator',
            csrf_token: 'csrf-token-123',
          }),
      });

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText('Not authenticated')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Login'));

    await waitFor(() => {
      expect(screen.getByText('User: test@example.com')).toBeInTheDocument();
    });

    // CSRF token should be stored
    expect(sessionStorage.getItem('eval_csrf_token')).toBe('csrf-token-123');
  });
});
