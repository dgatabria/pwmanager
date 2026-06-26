import { useState, useEffect, useCallback } from 'react'
import api from '../services/api'
import type { User, Group } from '../types'

export default function AdminUserManagement() {
  const [users, setUsers] = useState<User[]>([])
  const [groups, setGroups] = useState<Group[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [showResetPassword, setShowResetPassword] = useState<number | null>(null)
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [newUser, setNewUser] = useState({
    username: '',
    email: '',
    full_name: '',
    is_active: true,
    is_superuser: false,
  })
  const [showGroupModal, setShowGroupModal] = useState<number | null>(null)

  // Group management state
  const [activeSubTab, setActiveSubTab] = useState<'users' | 'groups'>('users')
  const [showCreateGroupModal, setShowCreateGroupModal] = useState(false)
  const [editingGroup, setEditingGroup] = useState<Group | null>(null)
  const [newGroup, setNewGroup] = useState({ name: '', description: '' })

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [usersData, groupsData] = await Promise.all([
        api.get<User[]>(`/api/admin/users${search ? `?search=${search}` : ''}`),
        api.get<Group[]>('/api/admin/groups'),
      ])
      setUsers(usersData)
      setGroups(groupsData)
    } catch (err: any) {
      setError(err.message || 'Failed to load data')
    } finally {
      setLoading(false)
    }
  }, [search])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const handleCreateUser = async () => {
    if (!newUser.username.trim() || !newUser.email.trim()) {
      setError('Username and email are required')
      return
    }
    try {
      await api.post('/api/admin/users', newUser)
      setShowCreateModal(false)
      setNewUser({
        username: '',
        email: '',
        full_name: '',
        is_active: true,
        is_superuser: false,
      })
      await fetchData()
    } catch (err: any) {
      setError(err.message || 'Failed to create user')
    }
  }

  const handleToggleActive = async (userId: number) => {
    try {
      await api.post(`/api/admin/users/${userId}/toggle-active`, {})
      await fetchData()
    } catch (err: any) {
      setError(err.message || 'Failed to update user')
    }
  }

  const handleResetPassword = async (userId: number) => {
    if (newPassword !== confirmPassword) {
      setError('Passwords do not match')
      return
    }
    // Client-side validation (server will also validate)
    if (newPassword.length < 12) {
      setError('Password must be at least 12 characters')
      return
    }
    if (!/[A-Z]/.test(newPassword)) {
      setError('Password must contain at least one uppercase letter')
      return
    }
    if (!/[a-z]/.test(newPassword)) {
      setError('Password must contain at least one lowercase letter')
      return
    }
    if (!/[0-9]/.test(newPassword)) {
      setError('Password must contain at least one digit')
      return
    }
    if (!/[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?`~]/.test(newPassword)) {
      setError('Password must contain at least one special character')
      return
    }
    try {
      await api.post(`/api/admin/users/${userId}/reset-password`, {
        new_password: newPassword,
      })
      setShowResetPassword(null)
      setNewPassword('')
      setConfirmPassword('')
    } catch (err: any) {
      setError(err.message || 'Failed to reset password')
    }
  }

  const handleDeleteUser = async (userId: number) => {
    if (!confirm('Are you sure you want to soft-delete this user? They will be marked as deleted but their data will be preserved. Pass confirm=true to proceed.')) return
    try {
      await api.delete(`/api/admin/users/${userId}?confirm=true`)
      await fetchData()
    } catch (err: any) {
      setError(err.message || 'Failed to delete user')
    }
  }

  const handleAddToGroup = async (userId: number, groupId: number) => {
    try {
      await api.post(`/api/admin/users/${userId}/groups/${groupId}`, {})
      setShowGroupModal(null)
      await fetchData()
    } catch (err: any) {
      setError(err.message || 'Failed to add user to group')
    }
  }

  const handleRemoveFromGroup = async (userId: number, groupId: number) => {
    try {
      await api.delete(`/api/admin/users/${userId}/groups/${groupId}`)
      await fetchData()
    } catch (err: any) {
      setError(err.message || 'Failed to remove user from group')
    }
  }

  const getUserGroups = (userId: number) => {
    return groups.filter(g => g.user_ids?.includes(userId))
  }

  // ─── Group Management Handlers ────────────────────────────────────

  const handleCreateGroup = async () => {
    if (!newGroup.name.trim()) {
      setError('Group name is required')
      return
    }
    try {
      await api.post('/api/admin/groups', newGroup)
      setShowCreateGroupModal(false)
      setNewGroup({ name: '', description: '' })
      await fetchData()
    } catch (err: any) {
      setError(err.message || 'Failed to create group')
    }
  }

  const handleUpdateGroup = async () => {
    if (!editingGroup) return
    if (!editingGroup.name.trim()) {
      setError('Group name is required')
      return
    }
    try {
      await api.put(`/api/admin/groups/${editingGroup.id}`, {
        name: editingGroup.name,
        description: editingGroup.description || null,
        is_active: editingGroup.is_active,
      })
      setEditingGroup(null)
      await fetchData()
    } catch (err: any) {
      setError(err.message || 'Failed to update group')
    }
  }

  const handleDeleteGroup = async (groupId: number) => {
    if (!confirm('Are you sure you want to delete this group? Users will be removed from it.')) return
    try {
      await api.delete(`/api/admin/groups/${groupId}`)
      await fetchData()
    } catch (err: any) {
      setError(err.message || 'Failed to delete group')
    }
  }

  const handleToggleGroupActive = async (groupId: number) => {
    const group = groups.find(g => g.id === groupId)
    if (!group) return
    try {
      await api.put(`/api/admin/groups/${groupId}`, { is_active: !group.is_active })
      await fetchData()
    } catch (err: any) {
      setError(err.message || 'Failed to update group')
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-900">User & Group Management</h1>
      </div>

      {/* Sub-tabs */}
      <div className="flex gap-2">
        <button
          onClick={() => setActiveSubTab('users')}
          className={`px-4 py-2 rounded-lg font-medium transition ${
            activeSubTab === 'users' ? 'bg-blue-600 text-white' : 'bg-white text-gray-700 hover:bg-gray-100'
          }`}
        >
          <span className="flex items-center gap-2">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
            Users
          </span>
        </button>
        <button
          onClick={() => setActiveSubTab('groups')}
          className={`px-4 py-2 rounded-lg font-medium transition ${
            activeSubTab === 'groups' ? 'bg-blue-600 text-white' : 'bg-white text-gray-700 hover:bg-gray-100'
          }`}
        >
          <span className="flex items-center gap-2">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.858M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.858M7 20H2v-2a3 3 0 015.356-1.858M7 20v-2c0-.656.126-1.283.356-1.858m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
            </svg>
            Groups
          </span>
        </button>
      </div>

      {/* Users sub-tab */}
      {activeSubTab === 'users' && (
        <>
          <div className="flex justify-between items-center">
            <button
              onClick={() => setShowCreateModal(true)}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition flex items-center gap-2"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              Create User
            </button>
          </div>

      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm">
          {error}
          <button onClick={() => setError('')} className="ml-2 font-semibold">✕</button>
        </div>
      )}

      <input
        type="text"
        placeholder="Search users..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
      />

      {loading ? (
        <div className="p-8 text-center text-gray-500">Loading...</div>
      ) : (
        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Username</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Email</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Groups</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {users.map((user) => (
                <tr key={user.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-gray-900">{user.username}</span>
                      {user.is_superuser && (
                        <span className="px-2 py-0.5 text-xs font-semibold bg-red-100 text-red-700 rounded-full">
                          Admin
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">{user.email}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-1 text-xs font-medium rounded-full ${
                      user.is_active ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                    }`}>
                      {user.is_active ? 'Active' : 'Blocked'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {getUserGroups(user.id).map(g => (
                      <span key={g.id} className="inline-block px-2 py-1 bg-blue-50 text-blue-700 rounded text-xs mr-1 mb-1">
                        {g.name}
                        <button
                          onClick={() => handleRemoveFromGroup(user.id, g.id)}
                          className="ml-1 text-red-600 hover:text-red-800"
                        >
                          ×
                        </button>
                      </span>
                    ))}
                    <button
                      onClick={() => setShowGroupModal(user.id)}
                      className="text-xs text-blue-600 hover:text-blue-800"
                    >
                      + Add
                    </button>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={() => handleToggleActive(user.id)}
                        className={`px-2 py-1 text-xs rounded ${
                          user.is_active
                            ? 'bg-yellow-100 text-yellow-700 hover:bg-yellow-200'
                            : 'bg-green-100 text-green-700 hover:bg-green-200'
                        }`}
                      >
                        {user.is_active ? 'Block' : 'Unblock'}
                      </button>
                      <button
                        onClick={() => setShowResetPassword(user.id)}
                        className="px-2 py-1 text-xs bg-purple-100 text-purple-700 rounded hover:bg-purple-200"
                      >
                        Reset Password
                      </button>
                      {user.id !== 1 && (
                        <button
                          onClick={() => handleDeleteUser(user.id)}
                          className="px-2 py-1 text-xs bg-red-100 text-red-700 rounded hover:bg-red-200"
                        >
                          Delete
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create User Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-md m-4 p-6">
            <h2 className="text-xl font-bold text-gray-900 mb-4">Create New User</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Username *</label>
                <input
                  type="text"
                  value={newUser.username}
                  onChange={(e) => setNewUser({ ...newUser, username: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Email *</label>
                <input
                  type="email"
                  value={newUser.email}
                  onChange={(e) => setNewUser({ ...newUser, email: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Full Name</label>
                <input
                  type="text"
                  value={newUser.full_name || ''}
                  onChange={(e) => setNewUser({ ...newUser, full_name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                />
              </div>
              <div className="flex gap-4">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={newUser.is_active}
                    onChange={(e) => setNewUser({ ...newUser, is_active: e.target.checked })}
                    className="rounded border-gray-300"
                  />
                  <span className="text-sm text-gray-700">Active</span>
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={newUser.is_superuser}
                    onChange={(e) => setNewUser({ ...newUser, is_superuser: e.target.checked })}
                    className="rounded border-gray-300"
                  />
                  <span className="text-sm text-gray-700">Superuser</span>
                </label>
              </div>
              <div className="flex justify-end gap-3 pt-4">
                <button
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 text-sm text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200"
                >
                  Cancel
                </button>
                <button
                  onClick={handleCreateUser}
                  className="px-4 py-2 text-sm text-white bg-blue-600 rounded-lg hover:bg-blue-700"
                >
                  Create
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Reset Password Modal */}
      {showResetPassword && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-md m-4 p-6">
            <h2 className="text-xl font-bold text-gray-900 mb-4">Reset Password</h2>
            <div className="space-y-4">
              <div className="p-3 bg-purple-50 border border-purple-200 rounded-lg">
                <p className="text-sm font-medium text-purple-800 mb-1">Password requirements:</p>
                <ul className="text-xs text-purple-700 list-disc list-inside space-y-0.5">
                  <li>At least 12 characters</li>
                  <li>One uppercase letter</li>
                  <li>One lowercase letter</li>
                  <li>One digit</li>
                  <li>One special character (!@#$%^&*...)</li>
                </ul>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">New Password</label>
                <input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 outline-none"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Confirm Password</label>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 outline-none"
                />
              </div>
              <div className="flex justify-end gap-3 pt-4">
                <button
                  onClick={() => setShowResetPassword(null)}
                  className="px-4 py-2 text-sm text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200"
                >
                  Cancel
                </button>
                <button
                  onClick={() => handleResetPassword(showResetPassword)}
                  className="px-4 py-2 text-sm text-white bg-purple-600 rounded-lg hover:bg-purple-700"
                >
                  Reset
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Add to Group Modal */}
      {showGroupModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-md m-4 p-6">
            <h2 className="text-xl font-bold text-gray-900 mb-4">Add User to Group</h2>
            <div className="space-y-3">
              {groups.map((group) => (
                <button
                  key={group.id}
                  onClick={() => handleAddToGroup(showGroupModal, group.id)}
                  className="w-full text-left px-4 py-3 bg-gray-50 hover:bg-gray-100 rounded-lg transition"
                >
                  <span className="font-medium">{group.name}</span>
                  {group.description && <span className="text-sm text-gray-500 ml-2">{group.description}</span>}
                </button>
              ))}
            </div>
            <div className="flex justify-end mt-4">
              <button
                onClick={() => setShowGroupModal(null)}
                className="px-4 py-2 text-sm text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
      </>
      )}

      {/* Groups sub-tab */}
      {activeSubTab === 'groups' && (
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">User Groups (RBAC)</h2>
              <p className="text-sm text-gray-500">Manage user groups for role-based access control. Groups are used to control access to secret groups.</p>
            </div>
            <button
              onClick={() => {
                setEditingGroup(null)
                setNewGroup({ name: '', description: '' })
                setShowCreateGroupModal(true)
              }}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition flex items-center gap-2"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              Create Group
            </button>
          </div>

          {groups.length === 0 ? (
            <div className="bg-white rounded-lg border border-gray-200 p-8 text-center">
              <p className="text-gray-500">No groups configured yet.</p>
              <button
                onClick={() => setShowCreateGroupModal(true)}
                className="text-blue-600 hover:text-blue-700 text-sm font-medium mt-2"
              >
                + Create your first group
              </button>
            </div>
          ) : (
            <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
              <table className="w-full">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Description</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Members</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {groups.map((group) => (
                    <tr key={group.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3">
                        {editingGroup?.id === group.id ? (
                          <input
                            type="text"
                            value={editingGroup.name}
                            onChange={(e) => setEditingGroup({ ...editingGroup, name: e.target.value })}
                            className="w-full px-2 py-1 border border-blue-300 rounded text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                            autoFocus
                          />
                        ) : (
                          <span className="font-medium text-gray-900">{group.name}</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600">
                        {editingGroup?.id === group.id ? (
                          <input
                            type="text"
                            value={editingGroup.description || ''}
                            onChange={(e) => setEditingGroup({ ...editingGroup, description: e.target.value || null })}
                            className="w-full px-2 py-1 border border-blue-300 rounded text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                          />
                        ) : (
                          <span className="text-gray-500">{group.description || '—'}</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600">
                        <span className="inline-block px-2 py-1 bg-blue-50 text-blue-700 rounded text-xs">
                          {group.user_ids?.length || 0} users
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`px-2 py-1 text-xs font-medium rounded-full ${
                          group.is_active ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                        }`}>
                          {group.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex items-center justify-end gap-2">
                          {editingGroup?.id === group.id ? (
                            <>
                              <button
                                onClick={handleUpdateGroup}
                                className="px-2 py-1 text-xs bg-green-100 text-green-700 rounded hover:bg-green-200"
                              >
                                Save
                              </button>
                              <button
                                onClick={() => setEditingGroup(null)}
                                className="px-2 py-1 text-xs bg-gray-100 text-gray-700 rounded hover:bg-gray-200"
                              >
                                Cancel
                              </button>
                            </>
                          ) : (
                            <>
                              <button
                                onClick={() => setEditingGroup({ ...group })}
                                className="px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded hover:bg-blue-200"
                              >
                                Edit
                              </button>
                              <button
                                onClick={() => handleToggleGroupActive(group.id)}
                                className={`px-2 py-1 text-xs rounded ${
                                  group.is_active
                                    ? 'bg-yellow-100 text-yellow-700 hover:bg-yellow-200'
                                    : 'bg-green-100 text-green-700 hover:bg-green-200'
                                }`}
                              >
                                {group.is_active ? 'Deactivate' : 'Activate'}
                              </button>
                              <button
                                onClick={() => handleDeleteGroup(group.id)}
                                className="px-2 py-1 text-xs bg-red-100 text-red-700 rounded hover:bg-red-200"
                              >
                                Delete
                              </button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Create Group Modal */}
      {showCreateGroupModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-md m-4 p-6">
            <h2 className="text-xl font-bold text-gray-900 mb-4">
              {editingGroup ? 'Edit Group' : 'Create New Group'}
            </h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Group Name *</label>
                <input
                  type="text"
                  value={editingGroup ? editingGroup.name : newGroup.name}
                  onChange={(e) => {
                    if (editingGroup) {
                      setEditingGroup({ ...editingGroup, name: e.target.value })
                    } else {
                      setNewGroup({ ...newGroup, name: e.target.value })
                    }
                  }}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                  autoFocus
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                <input
                  type="text"
                  value={editingGroup ? (editingGroup.description || '') : newGroup.description}
                  onChange={(e) => {
                    if (editingGroup) {
                      setEditingGroup({ ...editingGroup, description: e.target.value || null })
                    } else {
                      setNewGroup({ ...newGroup, description: e.target.value })
                    }
                  }}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                />
              </div>
              <div className="flex justify-end gap-3 pt-4">
                <button
                  onClick={() => {
                    setShowCreateGroupModal(false)
                    setEditingGroup(null)
                    setNewGroup({ name: '', description: '' })
                  }}
                  className="px-4 py-2 text-sm text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200"
                >
                  Cancel
                </button>
                <button
                  onClick={editingGroup ? handleUpdateGroup : handleCreateGroup}
                  className="px-4 py-2 text-sm text-white bg-blue-600 rounded-lg hover:bg-blue-700"
                >
                  {editingGroup ? 'Update' : 'Create'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
