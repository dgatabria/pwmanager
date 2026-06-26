// ─── CSRF Token Management ──────────────────────────────────────────
let csrfToken: string | null = null

/**
 * Fetch a fresh CSRF token from the server and cache it.
 * The token is also stored in an httpOnly cookie by the server.
 */
async function ensureCsrfToken(): Promise<string> {
  if (csrfToken) return csrfToken

  try {
    const res = await fetch('/api/auth/csrf-token', {
      method: 'GET',
      credentials: 'include',
    })
    if (res.ok) {
      const data = await res.json()
      csrfToken = data.csrf_token ?? ''
    }
  } catch {
    // If we can't fetch a token, proceed without CSRF protection
    // (e.g., during initial page load before the backend is ready)
  }
  return csrfToken ?? ''
}

const api = {
  async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    // Attach CSRF token to state-changing requests
    const isUnsafeMethod = options.method && ['POST', 'PUT', 'DELETE', 'PATCH'].includes(options.method)
    if (isUnsafeMethod) {
      csrfToken = await ensureCsrfToken()
    }

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string> | undefined),
    }

    // Attach CSRF token header for unsafe methods
    if (isUnsafeMethod && csrfToken) {
      headers['X-CSRF-Token'] = csrfToken
    }

    const response = await fetch(`${endpoint}`, {
      ...options,
      credentials: 'include', // Send httpOnly cookies
      headers,
    })

    if (response.status === 401) {
      // Token expired or invalid — redirect to login
      window.location.href = '/login'
      throw new Error('Unauthorized')
    }

    // If CSRF token was invalidated (403), refresh it and retry once
    if (response.status === 403 && isUnsafeMethod) {
      const body = await response.json().catch(() => ({}))
      if (body.detail?.includes?.('CSRF')) {
        csrfToken = null // Force refresh
        return api.request<T>(endpoint, options)
      }
      throw new Error(body.detail || 'Forbidden')
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Request failed' }))
      throw new Error(error.detail || 'Request failed')
    }

    if (response.status === 204) {
      return {} as T
    }

    return response.json()
  },

  get: <T>(endpoint: string) => api.request<T>(endpoint, { method: 'GET' }),
  post: <T>(endpoint: string, body: unknown) =>
    api.request<T>(endpoint, { method: 'POST', body: JSON.stringify(body) }),
  put: <T>(endpoint: string, body: unknown) =>
    api.request<T>(endpoint, { method: 'PUT', body: JSON.stringify(body) }),
  delete: (endpoint: string) =>
    api.request<void>(endpoint, { method: 'DELETE' }),

  // Audit-logged endpoints
  getMaskedSecret: <T>(secretId: number) =>
    api.request<T>(`/api/secrets/${secretId}/masked`, { method: 'GET' }),
  revealSecret: <T>(secretId: number) =>
    api.request<T>(`/api/secrets/${secretId}/reveal`, { method: 'GET' }),
  copySecret: <T>(secretId: number) =>
    api.request<T>(`/api/secrets/${secretId}/copy`, { method: 'POST' }),
}

export default api
