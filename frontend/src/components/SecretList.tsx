import type { Secret } from '../types'

interface Props {
  secrets: Secret[]
  selectedId: number | null
  onSelect: (secret: Secret) => void
  onEdit: (secret: Secret) => void
  onDelete: (id: number) => void
}

const typeIcons: Record<Secret['secret_type'], string> = {
  ssh_key: '🔑',
  password: '🔒',
  credential: '👤',
  api_key: '🔐',
  custom: '📄',
}

export default function SecretList({ secrets, selectedId, onSelect, onEdit, onDelete }: Props) {
  if (secrets.length === 0) {
    return (
      <div className="p-4 text-center text-gray-400 text-sm">
        No secrets found
      </div>
    )
  }

  return (
    <div className="divide-y divide-gray-100">
      {secrets.map((secret) => (
        <div
          key={secret.id}
          className={`group flex items-start gap-3 p-3 cursor-pointer hover:bg-gray-50 transition ${
            selectedId === secret.id ? 'bg-blue-50 border-l-4 border-blue-500' : 'border-l-4 border-transparent'
          }`}
          onClick={() => onSelect(secret)}
        >
          <div className="text-2xl shrink-0 mt-0.5">
            {typeIcons[secret.secret_type] || '📄'}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between gap-2">
              <h3 className="text-sm font-semibold text-gray-900 truncate">
                {secret.title}
              </h3>
              <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition shrink-0">
                <button
                  onClick={(e) => { e.stopPropagation(); onEdit(secret); }}
                  className="p-1 text-gray-400 hover:text-blue-600 rounded"
                  title="Edit"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                  </svg>
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); onDelete(secret.id); }}
                  className="p-1 text-gray-400 hover:text-red-600 rounded"
                  title="Delete"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              </div>
            </div>
            {secret.description && (
              <p className="text-xs text-gray-500 truncate mt-0.5">
                {secret.description}
              </p>
            )}
            <div className="flex items-center gap-2 mt-1">
              <span className="text-xs text-gray-400">
                {secret.secret_type.replace('_', ' ')}
              </span>
              {secret.username && (
                <span className="text-xs text-gray-400">| {secret.username}</span>
              )}
              <span className="text-xs text-gray-400 ml-auto">
                {new Date(secret.updated_at).toLocaleDateString()}
              </span>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}
