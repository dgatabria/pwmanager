import { useState, useEffect } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { useNavigate } from 'react-router-dom'
import api from '../services/api'
import type { APIToken, APITokenCreateResponse, APITokenRecycleResponse, Group } from '../types'

export default function Preferences() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState<'tokens' | 'profile'>('tokens')
  const [apiTokens, setApiTokens] = useState<APIToken[]>([])
  const [userGroups, setUserGroups] = useState<Group[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showNewTokenModal, setShowNewTokenModal] = useState(false)
  const [newTokenName, setNewTokenName] = useState('')
  const [newTokenDesc, setNewTokenDesc] = useState('')
  const [generatedToken, setGeneratedToken] = useState<APITokenCreateResponse | null>(null)
  const [tokenToDelete, setTokenToDelete] = useState<number | null>(null)
  const [tokenToRecycle, setTokenToRecycle] = useState<{ id: number; name: string } | null>(null)
  const [recycleTokenKey, setRecycleTokenKey] = useState('')
  const [recycleResponse, setRecycleResponse] = useState<APITokenRecycleResponse | null>(null)

  // Fetch API tokens and user groups
  useEffect(() => {
    fetchTokens()
    fetchGroups()
  }, [])

  const fetchGroups = async () => {
    try {
      const groups = await api.get<Group[]>('/api/auth/user-groups')
      setUserGroups(groups)
    } catch (err: any) {
      console.error('Failed to load user groups:', err)
    }
  }

  const fetchTokens = async () => {
    setLoading(true)
    setError('')
    try {
      const tokens = await api.get<APIToken[]>('/api/api-tokens')
      setApiTokens(tokens)
    } catch (err: any) {
      setError(err.message || 'Failed to load API tokens')
    } finally {
      setLoading(false)
    }
  }

  // Generate new token
  const handleGenerateToken = async () => {
    if (!newTokenName.trim()) {
      setError('Token name is required')
      return
    }

    setError('')
    try {
      const response = await api.post<APITokenCreateResponse>('/api/api-tokens/generate', {
        name: newTokenName.trim(),
        description: newTokenDesc.trim() || null,
      })
      setGeneratedToken(response)
      setNewTokenName('')
      setNewTokenDesc('')
      await fetchTokens()
    } catch (err: any) {
      setError(err.message || 'Failed to generate token')
    }
  }

  // Revoke token
  const handleRevokeToken = async (tokenId: number) => {
    try {
      await api.delete(`/api/api-tokens/${tokenId}`)
      setTokenToDelete(null)
      await fetchTokens()
    } catch (err: any) {
      setError(err.message || 'Failed to revoke token')
    }
  }

  // Recycle token
  const handleRecycleToken = async () => {
    if (!recycleTokenKey.trim()) {
      setError('API key is required')
      return
    }

    setError('')
    try {
      const response = await api.post<APITokenRecycleResponse>('/api/api-tokens/recycle', {
        api_key: recycleTokenKey.trim(),
      })
      setRecycleResponse(response)
      setRecycleTokenKey('')
      setTokenToRecycle(null)
      await fetchTokens()
    } catch (err: any) {
      setError(err.message || (err.message === 'Invalid or expired token' ? 'Invalid API key' : 'Failed to recycle token'))
    }
  }

  // Copy generated token to clipboard
  const handleCopyToken = () => {
    if (generatedToken?.token) {
      navigator.clipboard.writeText(generatedToken.token)
    }
  }

  return (
    <div className="h-screen flex flex-col bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-4 shrink-0">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
          <button
            onClick={() => navigate('/')}
            className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition"
          >
            ← Back to Dashboard
          </button>
        </div>
      </header>

      {/* Tabs */}
      <div className="px-6 pt-4">
        <div className="flex gap-2">
          <button
            onClick={() => setActiveTab('tokens')}
            className={`px-4 py-2 rounded-lg font-medium transition ${
              activeTab === 'tokens' ? 'bg-blue-600 text-white' : 'bg-white text-gray-700 hover:bg-gray-100'
            }`}
          >
            API Tokens
          </button>
          <button
            onClick={() => setActiveTab('profile')}
            className={`px-4 py-2 rounded-lg font-medium transition ${
              activeTab === 'profile' ? 'bg-blue-600 text-white' : 'bg-white text-gray-700 hover:bg-gray-100'
            }`}
          >
            Profile
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {activeTab === 'tokens' && (
          <div className="max-w-4xl mx-auto space-y-6">
            {/* Info */}
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <h2 className="text-lg font-semibold text-blue-900 mb-2">API Programmatic Access</h2>
              <p className="text-sm text-blue-700">
                Generate API tokens to access the Password Manager programmatically. Each token grants the same
                permissions as your user session. Use the token with <code className="bg-blue-100 px-1 py-0.5 rounded">Authorization: Bearer pm_xxx</code> header.
              </p>
            </div>

            {/* Generate Token Button */}
            <div className="flex justify-end">
              <button
                onClick={() => setShowNewTokenModal(true)}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition flex items-center gap-2"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                Generate New Token
              </button>
            </div>

            {/* Error */}
            {error && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm">
                {error}
              </div>
            )}

            {/* Token List */}
            {loading ? (
              <div className="text-center py-8 text-gray-500">Loading...</div>
            ) : (
              <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
                <table className="w-full">
                  <thead className="bg-gray-50 border-b border-gray-200">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Description</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Created</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Last Used</th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {apiTokens.length === 0 ? (
                      <tr>
                        <td colSpan={6} className="px-4 py-8 text-center text-gray-400">
                          No API tokens yet. Generate one to get started.
                        </td>
                      </tr>
                    ) : (
                      apiTokens.map((token) => (
                        <tr key={token.id} className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-sm font-medium text-gray-900">{token.name}</td>
                          <td className="px-4 py-3 text-sm text-gray-500">{token.description || '-'}</td>
                          <td className="px-4 py-3">
                            <span className={`text-xs px-2 py-1 rounded-full ${token.is_active ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                              {token.is_active ? 'Active' : 'Revoked'}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-500">{new Date(token.created_at).toLocaleDateString()}</td>
                          <td className="px-4 py-3 text-sm text-gray-500">{token.last_used_at ? new Date(token.last_used_at).toLocaleDateString() : 'Never'}</td>
                          <td className="px-4 py-3 text-right">
                            <div className="flex justify-end gap-2">
                              <button
                                onClick={() => setTokenToRecycle({ id: token.id, name: token.name })}
                                className="text-xs text-amber-600 hover:text-amber-700"
                                title="Recycle token"
                              >
                                ♻️
                              </button>
                              <button
                                onClick={() => setTokenToDelete(token.id)}
                                className="text-xs text-red-600 hover:text-red-700"
                                title="Revoke token"
                              >
                                🗑️
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {activeTab === 'profile' && (
          <div className="max-w-2xl mx-auto space-y-6">
            {/* Profile Card */}
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <h2 className="text-xl font-bold text-gray-900 mb-4">Profile</h2>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700">Username</label>
                  <p className="mt-1 text-gray-900">{user?.username}</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Email</label>
                  <p className="mt-1 text-gray-900">{user?.email}</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Full Name</label>
                  <p className="mt-1 text-gray-900">{user?.full_name || '-'}</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Role</label>
                  <p className="mt-1">
                    <span className={`inline-block px-2 py-1 text-xs font-medium rounded-full ${
                      user?.is_superuser ? 'bg-red-100 text-red-700' : 'bg-gray-100 text-gray-700'
                    }`}>
                      {user?.is_superuser ? 'Superuser' : 'User'}
                    </span>
                  </p>
                </div>
              </div>
            </div>

            {/* Groups Card */}
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <h2 className="text-xl font-bold text-gray-900 mb-4">Groups</h2>
              {userGroups.length === 0 ? (
                <p className="text-sm text-gray-500">You are not a member of any groups.</p>
              ) : (
                <div className="space-y-2">
                  {userGroups.map((group) => (
                    <div key={group.id} className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0">
                      <div>
                        <p className="text-sm font-medium text-gray-900">{group.name}</p>
                        <p className="text-xs text-gray-500">{group.description || 'No description'}</p>
                      </div>
                      <span className="inline-block px-2 py-1 text-xs font-medium rounded-full bg-blue-50 text-blue-700">
                        member
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Actions Card */}
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <h2 className="text-xl font-bold text-gray-900 mb-4">Account Actions</h2>
              <div className="space-y-3">
                <button
                  onClick={() => navigate('/change-password')}
                  className="w-full px-4 py-2 text-sm text-left text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition"
                >
                  Change Password
                </button>
                <button
                  onClick={() => {
                    logout()
                    navigate('/')
                  }}
                  className="w-full px-4 py-2 text-sm text-left text-white bg-red-600 rounded-lg hover:bg-red-700 transition"
                >
                  Sign Out
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Generate Token Modal */}
      {showNewTokenModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg m-4">
            <div className="p-6 border-b border-gray-200 flex justify-between items-center">
              <h2 className="text-xl font-bold text-gray-900">Generate New API Token</h2>
              <button onClick={() => setShowNewTokenModal(false)} className="text-gray-400 hover:text-gray-600">
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {generatedToken ? (
              <div className="p-6 space-y-4">
                <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg">
                  <p className="text-sm text-amber-800 font-medium">⚠️ {generatedToken.warning}</p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Your New API Token</label>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={generatedToken.token}
                      readOnly
                      className="flex-1 px-3 py-2 border border-gray-300 rounded-lg bg-gray-50 font-mono text-sm"
                    />
                    <button
                      onClick={handleCopyToken}
                      className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
                    >
                      Copy
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <form onSubmit={(e) => { e.preventDefault(); handleGenerateToken(); }} className="p-6 space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Token Name *</label>
                  <input
                    type="text"
                    value={newTokenName}
                    onChange={(e) => setNewTokenName(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                    placeholder="e.g., Production CI/CD"
                    required
                    autoFocus
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                  <textarea
                    value={newTokenDesc}
                    onChange={(e) => setNewTokenDesc(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                    placeholder="Optional description"
                    rows={2}
                  />
                </div>

                <div className="flex justify-end gap-3 pt-4 border-t border-gray-200">
                  <button
                    type="button"
                    onClick={() => setShowNewTokenModal(false)}
                    className="px-4 py-2 text-sm text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="px-4 py-2 text-sm text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition"
                  >
                    Generate Token
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}

      {/* Revoke Confirmation Modal */}
      {tokenToDelete !== null && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-md m-4 p-6">
            <h3 className="text-lg font-bold text-gray-900 mb-2">Revoke API Token</h3>
            <p className="text-sm text-gray-600 mb-4">
              Are you sure you want to revoke this token? It will no longer work for API access.
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setTokenToDelete(null)}
                className="px-4 py-2 text-sm text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition"
              >
                Cancel
              </button>
              <button
                onClick={() => handleRevokeToken(tokenToDelete)}
                className="px-4 py-2 text-sm text-white bg-red-600 rounded-lg hover:bg-red-700 transition"
              >
                Revoke
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Recycle Token Modal */}
      {tokenToRecycle && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg m-4">
            <div className="p-6 border-b border-gray-200 flex justify-between items-center">
              <h2 className="text-xl font-bold text-gray-900">Recycle API Token</h2>
              <button onClick={() => { setTokenToRecycle(null); setRecycleResponse(null); }} className="text-gray-400 hover:text-gray-600">
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="p-6 space-y-4">
              <p className="text-sm text-gray-600">
                To recycle token <strong>{tokenToRecycle.name}</strong>, provide the current valid API key.
                A new token will be generated and the old one will be revoked.
              </p>

              {recycleResponse && (
                <div className="p-4 bg-green-50 border border-green-200 rounded-lg space-y-2">
                  <p className="text-sm text-green-800 font-medium">✅ {recycleResponse.warning}</p>
                  <div>
                    <label className="block text-xs font-medium text-green-700 mb-1">New API Token</label>
                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={recycleResponse.new_token}
                        readOnly
                        className="flex-1 px-3 py-2 border border-green-300 rounded-lg bg-green-50 font-mono text-sm"
                      />
                      <button
                        onClick={() => navigator.clipboard.writeText(recycleResponse.new_token)}
                        className="px-3 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 text-sm"
                      >
                        Copy
                      </button>
                    </div>
                  </div>
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Current API Key *</label>
                <input
                  type="password"
                  value={recycleTokenKey}
                  onChange={(e) => setRecycleTokenKey(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-amber-500 outline-none font-mono"
                  placeholder="pm_xxxxxxxxxxxx"
                  required
                  autoFocus
                />
              </div>

              <div className="flex justify-end gap-3">
                <button
                  onClick={() => { setTokenToRecycle(null); setRecycleResponse(null); }}
                  className="px-4 py-2 text-sm text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition"
                >
                  Cancel
                </button>
                <button
                  onClick={handleRecycleToken}
                  className="px-4 py-2 text-sm text-white bg-amber-600 rounded-lg hover:bg-amber-700 transition"
                >
                  Recycle Token
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
