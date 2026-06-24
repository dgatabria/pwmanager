import { useState } from 'react'
import type { Secret, SecretGroup, SecretType } from '../types'

interface Props {
  initialData?: Secret
  secretGroups: SecretGroup[]
  onSubmit: (data: any) => void
  onCancel: () => void
}

const secretTypes: { value: SecretType; label: string }[] = [
  { value: 'password', label: 'Password' },
  { value: 'ssh_key', label: 'SSH Key' },
  { value: 'credential', label: 'Credential' },
  { value: 'api_key', label: 'API Key' },
  { value: 'custom', label: 'Custom' },
]

export default function SecretForm({ initialData, secretGroups, onSubmit, onCancel }: Props) {
  const [title, setTitle] = useState(initialData?.title || '')
  const [description, setDescription] = useState(initialData?.description || '')
  const [secretType, setSecretType] = useState<SecretType>(initialData?.secret_type || 'password')
  const [encryptedData, setEncryptedData] = useState(initialData?.decrypted_data || '')
  const [keyLength, setKeyLength] = useState(initialData?.key_length || 4096)
  const [username, setUsername] = useState(initialData?.username || '')
  const [url, setUrl] = useState(initialData?.url || '')
  const [groupId, setGroupId] = useState(initialData?.group_id || (secretGroups[0]?.id || 1))
  const [error, setError] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!title.trim() || !encryptedData.trim()) {
      setError('Title and secret value are required')
      return
    }
    onSubmit({
      title: title.trim(),
      description: description.trim() || null,
      secret_type: secretType,
      encrypted_data: encryptedData,
      key_length: secretType === 'ssh_key' ? keyLength : null,
      username: username.trim() || null,
      url: url.trim() || null,
      group_id: groupId,
    })
  }

  return (
    <form onSubmit={handleSubmit} className="p-6 space-y-4">
      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm">
          {error}
        </div>
      )}

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Title *</label>
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
          placeholder="e.g., Production Server SSH Key"
          required
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
        <input
          type="text"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
          placeholder="Optional description"
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Type *</label>
          <select
            value={secretType}
            onChange={(e) => setSecretType(e.target.value as SecretType)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
          >
            {secretTypes.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Group *</label>
          <select
            value={groupId}
            onChange={(e) => setGroupId(Number(e.target.value))}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
          >
            {secretGroups.map((g) => (
              <option key={g.id} value={g.id}>{g.name}</option>
            ))}
          </select>
        </div>
      </div>

      {(secretType === 'credential' || secretType === 'password') && (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Username</label>
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
            placeholder="Optional username"
          />
        </div>
      )}

      {secretType === 'ssh_key' && (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Key Length</label>
          <select
            value={keyLength}
            onChange={(e) => setKeyLength(Number(e.target.value))}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
          >
            <option value={2048}>2048 bits</option>
            <option value={4096}>4096 bits</option>
            <option value={8192}>8192 bits</option>
          </select>
        </div>
      )}

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          {secretType === 'ssh_key' ? 'Private Key' : 'Secret Value'} *
        </label>
        <textarea
          name="encrypted_data"
          value={encryptedData}
          onChange={(e) => setEncryptedData(e.target.value)}
          rows={secretType === 'ssh_key' ? 8 : 4}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none font-mono text-sm"
          placeholder={secretType === 'ssh_key' ? '-----BEGIN OPENSSH PRIVATE KEY-----...' : 'Enter the secret value'}
          required
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">URL</label>
        <input
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
          placeholder="https://..."
        />
      </div>

      <div className="flex justify-end gap-3 pt-4 border-t border-gray-200">
        <button
          type="button"
          onClick={onCancel}
          className="px-4 py-2 text-sm text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition"
        >
          Cancel
        </button>
        <button
          type="submit"
          className="px-4 py-2 text-sm text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition"
        >
          {initialData ? 'Update' : 'Create'}
        </button>
      </div>
    </form>
  )
}
