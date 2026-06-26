import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { useNavigate } from 'react-router-dom'
import api from '../services/api'
import type { Secret, SecretGroup, Group } from '../types'
import SecretList from '../components/SecretList'
import SecretDetail from '../components/SecretDetail'
import SecretForm from '../components/SecretForm'
import GroupSidebar from '../components/GroupSidebar'
import AddSecretButton from '../components/AddSecretButton'
import SearchBar from '../components/SearchBar'
import UserManagement from '../components/UserManagement'
import CreateSecretGroupModal from '../components/CreateSecretGroupModal'

export default function Dashboard() {
  const { logout } = useAuth()
  const navigate = useNavigate()

  // State
  const [secrets, setSecrets] = useState<Secret[]>([])
  const [secretGroups, setSecretGroups] = useState<SecretGroup[]>([])
  const [groups, setGroups] = useState<Group[]>([])
  const [selectedSecret, setSelectedSecret] = useState<Secret | null>(null)
  const [selectedGroupId, setSelectedGroupId] = useState<number | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [showCreateGroupModal, setShowCreateGroupModal] = useState(false)
  const [editingSecret, setEditingSecret] = useState<Secret | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [activeTab, setActiveTab] = useState<'secrets' | 'users'>('secrets')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // Get personal group ID for default selection
  const personalGroupId = secretGroups.find((g) => g.is_personal)?.id ?? null

  // Get selected group name for header
  const selectedGroupName = selectedGroupId
    ? secretGroups.find((g) => g.id === selectedGroupId)?.name ?? ''
    : ''

  // Fetch data
  const fetchData = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      let secretsUrl = '/api/secrets'
      if (selectedGroupId) {
        secretsUrl += `?group_id=${selectedGroupId}`
      }
      const [secretsData, userGroupsData, secretGroupsData] = await Promise.all([
        api.get<Secret[]>(secretsUrl),
        api.get<Group[]>('/api/auth/user-groups'),
        api.get<SecretGroup[]>('/api/secret-groups'),
      ])
      setSecrets(secretsData)
      setGroups(userGroupsData)
      setSecretGroups(secretGroupsData)
    } catch (err: any) {
      setError(err.message || 'Failed to load data')
    } finally {
      setLoading(false)
    }
  }, [selectedGroupId])

  // Auto-select personal group on first load
  useEffect(() => {
    if (selectedGroupId === null && personalGroupId) {
      setSelectedGroupId(personalGroupId)
    }
  }, [selectedGroupId, personalGroupId])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  // Handle secret selection
  const handleSelectSecret = async (secret: Secret) => {
    try {
      const detail = await api.get<Secret>(`/api/secrets/${secret.id}`)
      setSelectedSecret(detail)
    } catch (err: any) {
      setError(err.message)
    }
  }

  // Handle delete
  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this secret?')) return
    try {
      await api.delete(`/api/secrets/${id}`)
      setSecrets(prev => prev.filter(s => s.id !== id))
      setSelectedSecret(null)
      await fetchData()
    } catch (err: any) {
      setError(err.message)
    }
  }

  // Handle form submit
  const handleFormSubmit = async (data: any) => {
    try {
      if (editingSecret) {
        await api.put(`/api/secrets/${editingSecret.id}`, data)
      } else {
        await api.post(`/api/secrets`, data)
      }
      setShowForm(false)
      setEditingSecret(null)
      await fetchData()
    } catch (err: any) {
      setError(err.message)
    }
  }

  const handleEdit = (secret: Secret) => {
    setEditingSecret(secret)
    setShowForm(true)
  }

  // Handle group creation
  const handleCreateGroup = async () => {
    await fetchData()
    setShowCreateGroupModal(false)
  }

  // Handle secret group deletion
  const handleDeleteSecretGroup = async (groupId: number) => {
    try {
      await api.delete(`/api/secret-groups/${groupId}`)
      await fetchData()
    } catch (err: any) {
      setError(err.message)
    }
  }

  const handleAddSSHKey = async () => {
    try {
      const response = await api.post<any>('/api/secrets/ssh-key/generate', {
        key_length: 4096,
        comment: 'corporate-ssh-key',
      })

      const data = {
        title: `SSH Key - ${response.fingerprint.slice(-12)}`,
        secret_type: 'ssh_key',
        encrypted_data: response.private_key,
        key_length: response.key_length,
        group_id: selectedGroupId || personalGroupId || 0,
      }

      setEditingSecret(null)
      setShowForm(true)
      // Pre-fill the SSH key data
      setTimeout(() => {
        const textarea = document.querySelector('textarea[name="encrypted_data"]') as HTMLTextAreaElement
        if (textarea) {
          textarea.value = response.private_key
        }
        const titleInput = document.querySelector('input[name="title"]') as HTMLInputElement
        if (titleInput) {
          titleInput.value = data.title
        }
      }, 100)
    } catch (err: any) {
      setError(err.message)
    }
  }

  return (
    <div className="h-screen flex flex-col bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-4 py-2 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-4">
          <h1 className="text-lg font-bold text-gray-900 flex items-center gap-2">
            <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
            Password Manager
          </h1>
          <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
            <button
              onClick={() => setActiveTab('secrets')}
              className={`px-3 py-1 rounded-md text-sm font-medium transition ${
                activeTab === 'secrets' ? 'bg-white shadow text-gray-900' : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              Secrets
            </button>
            <button
              onClick={() => setActiveTab('users')}
              className={`px-3 py-1 rounded-md text-sm font-medium transition ${
                activeTab === 'users' ? 'bg-white shadow text-gray-900' : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              Users & Groups
            </button>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => navigate('/preferences')}
            className="px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition flex items-center gap-1"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            Settings
          </button>
          <button
            onClick={logout}
            className="px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition"
          >
            Sign Out
          </button>
        </div>
      </header>

      {/* Main content */}
      <div className="flex flex-1 overflow-hidden">
        {activeTab === 'secrets' ? (
          <>
            {/* Left sidebar - Secret Groups */}
            <GroupSidebar
              groups={secretGroups}
              userGroups={groups}
              selectedGroupId={selectedGroupId}
              onSelectGroup={setSelectedGroupId}
              onAddGroup={() => setShowCreateGroupModal(true)}
              onDeleteGroup={handleDeleteSecretGroup}
            />

            {/* Center - Secret List */}
            <div className="w-96 border-r border-gray-200 flex flex-col bg-white">
              <div className="p-3 border-b border-gray-200">
                {selectedGroupName && (
                  <p className="text-xs font-semibold text-blue-600 mb-2 truncate">
                    {selectedGroupName}
                  </p>
                )}
                <SearchBar
                  value={searchQuery}
                  onChange={setSearchQuery}
                  onSearch={fetchData}
                />
                <div className="flex gap-2 mt-2">
                  <AddSecretButton onClick={() => { setEditingSecret(null); setShowForm(true); }} />
                  <button
                    onClick={handleAddSSHKey}
                    className="px-3 py-1.5 text-sm bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition"
                    title="Generate new SSH key"
                  >
                    + SSH Key
                  </button>
                </div>
              </div>
              <div className="flex-1 overflow-y-auto">
                {loading ? (
                  <div className="p-4 text-center text-gray-500">Loading...</div>
                ) : error ? (
                  <div className="p-4 text-center text-red-500">{error}</div>
                ) : (
                  <SecretList
                    secrets={secrets}
                    selectedId={selectedSecret?.id || null}
                    onSelect={handleSelectSecret}
                    onEdit={handleEdit}
                    onDelete={handleDelete}
                  />
                )}
              </div>
            </div>

            {/* Right - Secret Detail */}
            <div className="flex-1 overflow-y-auto bg-gray-50">
              {selectedSecret ? (
                <SecretDetail
                  secret={selectedSecret}
                  onEdit={() => handleEdit(selectedSecret)}
                  onDelete={() => handleDelete(selectedSecret.id)}
                />
              ) : (
                <div className="h-full flex items-center justify-center text-gray-400">
                  <div className="text-center">
                    <svg className="w-16 h-16 mx-auto mb-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
                    </svg>
                    <p className="text-lg font-medium">Select a secret to view details</p>
                    <p className="text-sm mt-1">Choose from the list on the left</p>
                  </div>
                </div>
              )}
            </div>
          </>
        ) : (
          /* Users & Groups tab */
          <div className="flex-1 overflow-y-auto p-6">
            <UserManagement groups={groups} onRefresh={() => fetchData()} />
          </div>
        )}
      </div>

      {/* Secret Form Modal */}
      {showForm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-2xl max-h-[80vh] overflow-y-auto m-4">
            <div className="p-6 border-b border-gray-200 flex justify-between items-center">
              <h2 className="text-xl font-bold text-gray-900">
                {editingSecret ? 'Edit Secret' : 'New Secret'}
              </h2>
              <button onClick={() => { setShowForm(false); setEditingSecret(null); }} className="text-gray-400 hover:text-gray-600">
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <SecretForm
              initialData={editingSecret || undefined}
              secretGroups={secretGroups}
              onSubmit={handleFormSubmit}
              onCancel={() => { setShowForm(false); setEditingSecret(null); }}
            />
          </div>
        </div>
      )}

      {/* Create Secret Group Modal */}
      {showCreateGroupModal && (
        <CreateSecretGroupModal
          userGroups={groups}
          onClose={() => setShowCreateGroupModal(false)}
          onSuccess={handleCreateGroup}
        />
      )}
    </div>
  )
}
