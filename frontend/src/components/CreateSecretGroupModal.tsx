import { useState, useEffect } from 'react'
import api from '../services/api'
import type { Group, SecretGroup } from '../types'

interface Props {
  userGroups: Group[]
  onClose: () => void
  onSuccess: () => void
}

export default function CreateSecretGroupModal({ userGroups, onClose, onSuccess }: Props) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [selectedGroupId, setSelectedGroupId] = useState<number | null>(null)
  const [visibility, setVisibility] = useState<'private' | 'shared'>('private')
  const [selectedGroups, setSelectedGroups] = useState<number[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    // Auto-select first available group if none selected
    if (selectedGroupId === null && userGroups.length > 0) {
      setSelectedGroupId(userGroups[0].id)
    }
  }, [userGroups, selectedGroupId])

  const toggleGroup = (groupId: number) => {
    setSelectedGroups(prev =>
      prev.includes(groupId) ? prev.filter(id => id !== groupId) : [...prev, groupId]
    )
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    if (!selectedGroupId) return

    setLoading(true)
    setError('')

    try {
      await api.post<SecretGroup>('/api/secret-groups', {
        name: name.trim(),
        description: description.trim() || null,
        parent_id: null,
        group_id: selectedGroupId,
        member_group_ids: visibility === 'shared' ? selectedGroups : [],
      })
      onSuccess()
    } catch (err: any) {
      setError(err.message || 'Failed to create group')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg m-4">
        {/* Header */}
        <div className="p-6 border-b border-gray-200 flex justify-between items-center">
          <div>
            <h2 className="text-xl font-bold text-gray-900">New Secret Group</h2>
            <p className="text-sm text-gray-500 mt-1">Organize and control access to your secrets</p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          {/* Name */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Group Name <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="e.g., Production Servers"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition"
              autoFocus
              required
            />
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
            <textarea
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="What is this group for?"
              rows={2}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition resize-none"
            />
          </div>

          {/* Target Group */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Target Group <span className="text-red-500">*</span>
            </label>
            <select
              value={selectedGroupId || ''}
              onChange={e => setSelectedGroupId(Number(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition bg-white"
              required
            >
              <option value="">Select a group...</option>
              {userGroups.map(g => (
                <option key={g.id} value={g.id}>{g.name}</option>
              ))}
            </select>
          </div>

          {/* Visibility */}
          <div className="border border-gray-200 rounded-lg overflow-hidden">
            <div className="bg-gray-50 px-4 py-2 border-b border-gray-200">
              <h3 className="text-sm font-semibold text-gray-700">Visibility & Access</h3>
            </div>

            <div className="divide-y divide-gray-100">
              {/* Private */}
              <label className="flex items-center gap-3 px-4 py-3 hover:bg-gray-50 cursor-pointer transition">
                <input
                  type="radio"
                  name="visibility"
                  value="private"
                  checked={visibility === 'private'}
                  onChange={() => setVisibility('private')}
                  className="w-4 h-4 text-blue-600 border-gray-300 focus:ring-blue-500"
                />
                <div className="flex-1">
                  <span className="text-sm font-medium text-gray-900">Only me</span>
                  <p className="text-xs text-gray-500">This group is visible only to you</p>
                </div>
                <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">Private</span>
              </label>

              {/* Shared */}
              <label className="flex items-center gap-3 px-4 py-3 hover:bg-gray-50 cursor-pointer transition">
                <input
                  type="radio"
                  name="visibility"
                  value="shared"
                  checked={visibility === 'shared'}
                  onChange={() => setVisibility('shared')}
                  className="w-4 h-4 text-blue-600 border-gray-300 focus:ring-blue-500"
                />
                <div className="flex-1">
                  <span className="text-sm font-medium text-gray-900">Share with groups</span>
                  <p className="text-xs text-gray-500">Select which user groups can view this group</p>
                </div>
                <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">Shared</span>
              </label>
            </div>

            {/* Group selectors (only when shared) */}
            {visibility === 'shared' && userGroups.length > 0 && (
              <div className="p-4 bg-gray-50 border-t border-gray-200">
                <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">
                  Select groups to share with
                </p>
                <div className="space-y-1.5 max-h-48 overflow-y-auto">
                  {userGroups.map(g => (
                    <label
                      key={g.id}
                      className={`flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition ${
                        selectedGroups.includes(g.id) ? 'bg-blue-50 border border-blue-200' : 'hover:bg-gray-100 border border-transparent'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={selectedGroups.includes(g.id)}
                        onChange={() => toggleGroup(g.id)}
                        className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                      />
                      <span className="text-sm text-gray-700">{g.name}</span>
                    </label>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Error */}
          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-sm text-red-600">{error}</p>
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2.5 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 font-medium transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading || !name.trim() || !selectedGroupId}
              className="flex-1 px-4 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Creating...' : 'Create Group'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
