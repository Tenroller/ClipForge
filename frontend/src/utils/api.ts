/**
 * API utility with automatic auth token injection
 */

const API_BASE = (import.meta.env.VITE_API_BASE as string) || 'http://localhost:9000';

/**
 * Get the auth token from localStorage
 */
function getAuthToken(): string | null {
  return localStorage.getItem('auth_token');
}

/**
 * Create headers with auth token if available
 */
function createHeaders(customHeaders?: HeadersInit): Headers {
  const headers = new Headers(customHeaders);

  const token = getAuthToken();
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  return headers;
}

/**
 * Fetch wrapper that automatically includes auth token
 */
export async function apiFetch(
  endpoint: string,
  options?: RequestInit
): Promise<Response> {
  const url = endpoint.startsWith('http') ? endpoint : `${API_BASE}${endpoint}`;

  const headers = createHeaders(options?.headers);

  const response = await fetch(url, {
    ...options,
    headers,
  });

  // If we get a 401, clear the token and reload to login page
  if (response.status === 401) {
    localStorage.removeItem('auth_token');
    window.location.href = '/login';
  }

  return response;
}

/**
 * Convenience methods for different HTTP verbs
 */
export const api = {
  get: (endpoint: string, options?: RequestInit) =>
    apiFetch(endpoint, { ...options, method: 'GET' }),

  post: (endpoint: string, body?: any, options?: RequestInit) =>
    apiFetch(endpoint, {
      ...options,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
      body: body ? JSON.stringify(body) : undefined,
    }),

  put: (endpoint: string, body?: any, options?: RequestInit) =>
    apiFetch(endpoint, {
      ...options,
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
      body: body ? JSON.stringify(body) : undefined,
    }),

  delete: (endpoint: string, options?: RequestInit) =>
    apiFetch(endpoint, { ...options, method: 'DELETE' }),

  patch: (endpoint: string, body?: any, options?: RequestInit) =>
    apiFetch(endpoint, {
      ...options,
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
      body: body ? JSON.stringify(body) : undefined,
    }),
};

export { API_BASE };
