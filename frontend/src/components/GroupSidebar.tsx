import type { SecretGroup, Group } from '../types'

interface Props {
  groups: SecretGroup[]
  userGroups: Group[]
  selectedGroupId: 'personal' | number | null
  onSelectGroup: (id: 'personal' | number | null) => void
  onAddGroup: () => void
  onDeleteGroup?: (id: number) => void
}

export default function GroupSidebar({ groups, userGroups, selectedGroupId, onSelectGroup, onAddGroup, onDeleteGroup }: Props) {
  return (
    <div className="w-56 bg-white border-r border-gray-200 flex flex-col shrink-0 overflow-y-auto">
      {/* Header with Add button */}
      <div className="p-3 border-b border-gray-200 flex items-center justify-between">
        <h2 className="text-xs font-bold text-gray-500 uppercase tracking-wider">Secret Groups</h2>
        <button
          onClick={onAddGroup}
          className="p-1 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded transition"
          title="Create new secret group"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
        </button>
      </div>

      {/* Personal Secrets */}
      <div className="p-2">
        <button
          onClick={() => onSelectGroup('personal')}
          className={`w-full text-left px-3 py-2 rounded-lg text-sm font-medium transition ${
            selectedGroupId === 'personal'
              ? 'bg-blue-50 text-blue-700'
              : 'text-gray-700 hover:bg-gray-100'
          }`}
        >
          Personal Secrets
        </button>
      </div>

      {/* Secret Groups List */}
      <div className="px-2 pb-2 flex-1">
        {groups.length === 0 ? (
          <div className="px-3 py-4 text-center">
            <p className="text-xs text-gray-400">No groups yet</p>
            <button
              onClick={onAddGroup}
              className="text-xs text-blue-600 hover:text-blue-700 mt-1 font-medium"
            >
              + Create one
            </button>
          </div>
        ) : (
          groups.map((group) => (
            <div
              key={group.id}
              className={`mb-1 rounded-lg transition group relative ${
                selectedGroupId === group.id
                  ? 'bg-blue-50'
                  : 'hover:bg-gray-50'
              }`}
            >
              <button
                onClick={() => onSelectGroup(group.id)}
                className={`w-full text-left px-3 py-2 rounded-lg text-sm transition flex items-center gap-2 ${
                  selectedGroupId === group.id
                    ? 'text-blue-700 font-medium'
                    : 'text-gray-600'
                }`}
              >
                <span className="truncate flex-1">{group.name}</span>
                {/* Access badge */}
                {group.group_ids && group.group_ids.length > 0 ? (
                  <span className="shrink-0 text-[10px] bg-green-100 text-green-700 px-1.5 py-0.5 rounded-full" title="Shared">
                    S
                  </span>
                ) : (
                  <span className="shrink-0 text-[10px] bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded-full" title="Private">
                    P
                  </span>
                )}
              </button>
              {/* Delete button - only visible on hover, only for owner */}
              {onDeleteGroup && (
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    if (confirm(`Delete "${group.name}" and all secrets inside?`)) {
                      onDeleteGroup(group.id)
                    }
                  }}
                  className="absolute right-1 bottom-1 p-0.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded opacity-0 group-hover:opacity-100 transition"
                  title="Delete group"
                >
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              )}
              {/* Owner tooltip */}
              {group.owner_username && (
                <span className="absolute bottom-0.5 left-2 text-[9px] text-gray-400 opacity-0 group-hover:opacity-100 transition">
                  {group.owner_username}
                </span>
              )}
            </div>
          ))
        )}
      </div>

      {/* User Groups */}
      {userGroups.length > 0 && (
        <>
          <div className="p-3 border-t border-gray-200">
            <h2 className="text-xs font-bold text-gray-500 uppercase tracking-wider">User Groups</h2>
          </div>
          <div className="px-2 pb-3">
            {userGroups.map((g) => (
              <div
                key={g.id}
                className="px-3 py-2 text-sm text-gray-500"
              >
                {g.name}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
