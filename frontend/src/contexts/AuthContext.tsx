import { createContext, useContext, useState, useEffect, ReactNode } from 'react'

interface User {
  id: number
  username: string
  email: string
  full_name: string
  is_superuser: boolean
  personal_group_id: number | null
}

interface AuthContextType {
  user: User | null
  passwordChangeRequired: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  isAuthenticated: boolean
  isSuperuser: boolean
  isLoading: boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [passwordChangeRequired, setPasswordChangeRequired] = useState(false)
  const [isLoading, setIsLoading] = useState(true)

  // Fetch user info from server to verify token (cookie or Bearer header)
  // and get accurate role info.
  useEffect(() => {
    fetchUserInfo()
  }, [])

  const fetchUserInfo = async () => {
    setIsLoading(true)
    try {
      const response = await fetch('/api/auth/me', {
        method: 'GET',
        credentials: 'include', // Send httpOnly cookies
      })

      if (!response.ok) {
        setUser(null)
        return
      }

      const data = await response.json()
      setUser({
        id: data.id,
        username: data.username,
        email: data.email,
        full_name: data.full_name,
        is_superuser: data.is_superuser,
        personal_group_id: data.personal_group_id ?? null,
      })
    } catch {
      setUser(null)
    } finally {
      setIsLoading(false)
    }
  }

  const login = async (username: string, password: string) => {
    const response = await fetch('/api/auth/login', {
      method: 'POST',
      credentials: 'include', // Accept httpOnly cookies
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    })

    if (!response.ok) {
      const text = await response.text().catch(() => '')
      let detail = 'Login failed'
      try {
        const error = JSON.parse(text)
        detail = error.detail || detail
      } catch {
        detail = text.includes('<html') ? 'Server error — check backend logs' : detail
      }
      throw new Error(detail)
    }

    const data = await response.json()
    setPasswordChangeRequired(data.password_change_required ?? false)

    // Token is set as httpOnly cookie by the server.
    // The JSON response also contains the token for non-cookie clients.
    await fetchUserInfo()
  }

  const logout = async () => {
    try {
      await fetch('/api/auth/logout', {
        method: 'POST',
        credentials: 'include',
      })
    } catch {
      // Ignore errors — the cookie is already set to expire
    }
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, passwordChangeRequired, login, logout, isAuthenticated: !!user, isSuperuser: !!user?.is_superuser, isLoading }}>
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
