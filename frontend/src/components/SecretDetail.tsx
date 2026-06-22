import type { Secret } from '../types'

interface Props {
  secret: Secret
  onEdit: () => void
  onDelete: () => void
  onCopy: (text: string) => void
}

export default function SecretDetail({ secret, onEdit, onDelete, onCopy }: Props) {
  const isSSHKey = secret.secret_type === 'ssh_key'

  return (
    <div className="p-6 max-w-3xl mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{secret.title}</h1>
          <p className="text-gray-500 mt-1">{secret.description || 'No description'}</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={onEdit}
            className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
          >
            Edit
          </button>
          <button
            onClick={onDelete}
            className="px-3 py-1.5 text-sm bg-red-600 text-white rounded-lg hover:bg-red-700 transition"
          >
            Delete
          </button>
        </div>
      </div>

      {/* Meta info */}
      <div className="grid grid-cols-2 gap-4 mb-6">
        <div className="bg-white rounded-lg p-4 border border-gray-200">
          <span className="text-xs text-gray-500 uppercase tracking-wide">Type</span>
          <p className="text-sm font-medium mt-1 capitalize">{secret.secret_type.replace('_', ' ')}</p>
        </div>
        <div className="bg-white rounded-lg p-4 border border-gray-200">
          <span className="text-xs text-gray-500 uppercase tracking-wide">Group</span>
          <p className="text-sm font-medium mt-1">{secret.group_name || 'N/A'}</p>
        </div>
        {secret.username && (
          <div className="bg-white rounded-lg p-4 border border-gray-200">
            <span className="text-xs text-gray-500 uppercase tracking-wide">Username</span>
            <p className="text-sm font-medium mt-1">{secret.username}</p>
          </div>
        )}
        {secret.key_length && (
          <div className="bg-white rounded-lg p-4 border border-gray-200">
            <span className="text-xs text-gray-500 uppercase tracking-wide">Key Length</span>
            <p className="text-sm font-medium mt-1">{secret.key_length} bits</p>
          </div>
        )}
        {secret.url && (
          <div className="bg-white rounded-lg p-4 border border-gray-200 col-span-2">
            <span className="text-xs text-gray-500 uppercase tracking-wide">URL</span>
            <a href={secret.url} target="_blank" rel="noopener noreferrer" className="text-sm text-blue-600 hover:underline mt-1 block">
              {secret.url}
            </a>
          </div>
        )}
      </div>

      {/* Secret data */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <div className="px-4 py-3 bg-gray-50 border-b border-gray-200 flex justify-between items-center">
          <span className="text-sm font-medium text-gray-700">
            {isSSHKey ? 'Private Key' : 'Secret Value'}
          </span>
          <button
            onClick={() => onCopy(secret.decrypted_data || '')}
            className="text-xs text-blue-600 hover:text-blue-700 flex items-center gap-1"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
            </svg>
            Copy
          </button>
        </div>
        <div className="p-4">
          <pre className="text-sm text-gray-800 whitespace-pre-wrap break-all font-mono bg-gray-900 text-green-400 p-4 rounded-lg overflow-auto max-h-96">
            {secret.decrypted_data || 'No data'}
          </pre>
        </div>
      </div>

      {/* Timestamps */}
      <div className="mt-6 text-xs text-gray-400 flex gap-4">
        <span>Created: {new Date(secret.created_at).toLocaleString()}</span>
        <span>Updated: {new Date(secret.updated_at).toLocaleString()}</span>
      </div>
    </div>
  )
}
