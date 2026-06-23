const api = {
  async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...options.headers,
    }

    const response = await fetch(`/api${endpoint}`, {
      ...options,
      credentials: 'include', // Send httpOnly cookies
      headers,
    })

    if (response.status === 401) {
      // Token expired or invalid — redirect to login
      window.location.href = '/login'
      throw new Error('Unauthorized')
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
    api.request<T>(`/secrets/${secretId}/masked`, { method: 'GET' }),
  revealSecret: <T>(secretId: number) =>
    api.request<T>(`/secrets/${secretId}/reveal`, { method: 'GET' }),
  copySecret: <T>(secretId: number) =>
    api.request<T>(`/secrets/${secretId}/copy`, { method: 'POST' }),
}

export default api
