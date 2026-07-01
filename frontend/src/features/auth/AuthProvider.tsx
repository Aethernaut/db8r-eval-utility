import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from 'react';
import { useNavigate, useLocation } from 'react-router';
import { apiGet, apiPost, setCsrfToken, clearCsrfToken } from '@/api/client';

export type UserRole = 'admin' | 'annotator';

export interface User {
  userId: string;
  email: string;
  role: UserRole;
}

interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  isAdmin: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

interface LoginResponse {
  user_id: string;
  email: string;
  role: string;
  csrf_token: string;
}

interface MeResponse {
  user_id: string;
  email: string;
  role: string;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const navigate = useNavigate();
  const location = useLocation();

  const setUserFromResponse = useCallback((data: { user_id: string; email: string; role: string }) => {
    setUser({
      userId: data.user_id,
      email: data.email,
      role: data.role as UserRole,
    });
  }, []);

  // Fetch current user on mount
  const fetchUser = useCallback(async () => {
    try {
      const data = await apiGet<MeResponse>('/auth/me');
      setUserFromResponse(data);
    } catch {
      setUser(null);
      clearCsrfToken();
    } finally {
      setIsLoading(false);
    }
  }, [setUserFromResponse]);

  useEffect(() => {
    fetchUser();
  }, [fetchUser]);

  // Listen for unauthorized events (401 responses)
  useEffect(() => {
    const handleUnauthorized = () => {
      setUser(null);
      clearCsrfToken();
      if (location.pathname !== '/login' && !location.pathname.startsWith('/accept-invite')) {
        navigate('/login', { state: { from: location.pathname } });
      }
    };

    window.addEventListener('auth:unauthorized', handleUnauthorized);
    return () => window.removeEventListener('auth:unauthorized', handleUnauthorized);
  }, [navigate, location.pathname]);

  const login = useCallback(async (email: string, password: string) => {
    const data = await apiPost<LoginResponse>('/auth/login', { email, password });
    setCsrfToken(data.csrf_token);
    setUserFromResponse(data);
  }, [setUserFromResponse]);

  const logout = useCallback(async () => {
    try {
      await apiPost('/auth/logout');
    } finally {
      setUser(null);
      clearCsrfToken();
      navigate('/login');
    }
  }, [navigate]);

  const refresh = useCallback(async () => {
    await fetchUser();
  }, [fetchUser]);

  const value: AuthContextValue = {
    user,
    isLoading,
    isAuthenticated: user !== null,
    isAdmin: user?.role === 'admin',
    login,
    logout,
    refresh,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
