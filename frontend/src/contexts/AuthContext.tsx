import { createContext, useContext, useState, useEffect, ReactNode } from 'react'

interface User {
  id: number
  username: string
  email: string
  full_name: string
  is_superuser: boolean
}

interface AuthContextType {
  token: string | null
  user: User | null
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  isAuthenticated: boolean
  isSuperuser: boolean
  isLoading: boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

/**
 * Decode the JWT payload (base64url) to extract the exp claim.
 * Returns the expiration timestamp or null if the token is invalid.
 */
function decodeJwtPayload(token: string): { exp: number } | null {
  try {
    const parts = token.split('.')
    if (parts.length !== 3) return null
    const payload = atob(parts[1])
    const json = JSON.parse(payload)
    if (json && typeof json.exp === 'number') return json
  } catch {
    // Invalid token format
  }
  return null
}

/** Check if a JWT token has expired. */
function isTokenExpired(token: string): boolean {
  const payload = decodeJwtPayload(token)
  if (!payload) return true
  return Date.now() >= payload.exp * 1000
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null)
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(false)

  // Initialize token from localStorage and check expiration
  useEffect(() => {
    const stored = localStorage.getItem('token')
    if (stored && !isTokenExpired(stored)) {
      setToken(stored)
    } else {
      // Token expired or missing — clear it
      localStorage.removeItem('token')
    }
  }, [])

  // Fetch user info from server to verify token and get accurate role info
  useEffect(() => {
    if (token) {
      fetchUserInfo()
    } else {
      setUser(null)
    }
  }, [token])

  const fetchUserInfo = async () => {
    if (!token) {
      setUser(null)
      return
    }

    setIsLoading(true)
    try {
      const response = await fetch('/api/auth/me', {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
      })

      if (!response.ok) {
        // Token is invalid or expired
        logout()
        return
      }

      const data = await response.json()
      setUser({
        id: data.id,
        username: data.username,
        email: data.email,
        full_name: data.full_name,
        is_superuser: data.is_superuser,
      })
    } catch {
      // Network error, token will be invalidated on next API call
      setUser(null)
    } finally {
      setIsLoading(false)
    }
  }

  const login = async (username: string, password: string) => {
    const response = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    })

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Login failed')
    }

    const data = await response.json()
    setToken(data.access_token)
    localStorage.setItem('token', data.access_token)
  }

  const logout = () => {
    setToken(null)
    setUser(null)
    localStorage.removeItem('token')
  }

  return (
    <AuthContext.Provider value={{ token, user, login, logout, isAuthenticated: !!token, isSuperuser: !!user?.is_superuser, isLoading }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return context
}
