/**
 * Custom fetch wrapper for API calls.
 * - Includes credentials (cookies) for auth
 * - Adds CSRF token header on mutations
 * - Handles 401 responses
 */

// CSRF token storage (set after login, persisted in sessionStorage)
const CSRF_KEY = 'eval_csrf_token';

export function setCsrfToken(token: string): void {
  sessionStorage.setItem(CSRF_KEY, token);
}

export function getCsrfToken(): string | null {
  return sessionStorage.getItem(CSRF_KEY);
}

export function clearCsrfToken(): void {
  sessionStorage.removeItem(CSRF_KEY);
}

type RequestConfig = {
  url: string;
  method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  headers?: Record<string, string>;
  params?: Record<string, string>;
  data?: unknown;
  signal?: AbortSignal;
};

export async function customFetch<T>(config: RequestConfig): Promise<T> {
  const { url, method, headers = {}, params, data, signal } = config;

  // Build URL with query params
  let fullUrl = url;
  if (params) {
    const searchParams = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null) {
        searchParams.append(key, value);
      }
    }
    const queryString = searchParams.toString();
    if (queryString) {
      fullUrl += `?${queryString}`;
    }
  }

  // Build headers
  const requestHeaders: Record<string, string> = {
    ...headers,
  };

  // Add CSRF token for state-changing requests
  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
    const csrfToken = getCsrfToken();
    if (csrfToken) {
      requestHeaders['X-CSRF-Token'] = csrfToken;
    }
  }

  // Add Content-Type for requests with body
  if (data !== undefined) {
    requestHeaders['Content-Type'] = 'application/json';
  }

  const response = await fetch(fullUrl, {
    method,
    headers: requestHeaders,
    body: data !== undefined ? JSON.stringify(data) : undefined,
    credentials: 'include', // Always include cookies
    signal,
  });

  // Handle 401 - redirect to login
  if (response.status === 401) {
    clearCsrfToken();
    // Dispatch custom event for auth context to handle
    window.dispatchEvent(new CustomEvent('auth:unauthorized'));
    throw response;
  }

  // Handle non-OK responses
  if (!response.ok) {
    throw response;
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return undefined as T;
  }

  // Parse JSON response
  const contentType = response.headers.get('content-type');
  if (contentType?.includes('application/json')) {
    return response.json();
  }

  return response.text() as Promise<T>;
}

// Helper for simple GET requests (used in manual fetches)
export async function apiGet<T>(url: string, params?: Record<string, string>): Promise<T> {
  return customFetch<T>({ url, method: 'GET', params });
}

// Helper for POST requests
export async function apiPost<T>(url: string, data?: unknown): Promise<T> {
  return customFetch<T>({ url, method: 'POST', data });
}

// Helper for PUT requests
export async function apiPut<T>(url: string, data?: unknown): Promise<T> {
  return customFetch<T>({ url, method: 'PUT', data });
}

// Helper for DELETE requests
export async function apiDelete<T>(url: string): Promise<T> {
  return customFetch<T>({ url, method: 'DELETE' });
}
