import type { SecretGroup, Group } from '../types'

interface Props {
  groups: SecretGroup[]
  userGroups: Group[]
  selectedGroupId: number | null
  onSelectGroup: (id: number | null) => void
  onAddGroup: () => void
}

export default function GroupSidebar({ groups, userGroups, selectedGroupId, onSelectGroup, onAddGroup }: Props) {
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

      {/* All Secrets */}
      <div className="p-2">
        <button
          onClick={() => onSelectGroup(null)}
          className={`w-full text-left px-3 py-2 rounded-lg text-sm font-medium transition ${
            selectedGroupId === null
              ? 'bg-blue-50 text-blue-700'
              : 'text-gray-700 hover:bg-gray-100'
          }`}
        >
          All Secrets
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
            <button
              key={group.id}
              onClick={() => onSelectGroup(group.id)}
              className={`w-full text-left px-3 py-2 rounded-lg text-sm transition group relative ${
                selectedGroupId === group.id
                  ? 'bg-blue-50 text-blue-700 font-medium'
                  : 'text-gray-600 hover:bg-gray-50'
              }`}
            >
              <div className="flex items-center gap-2">
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
              </div>
              {/* Owner tooltip */}
              {group.owner_username && (
                <span className="absolute bottom-0.5 right-1 text-[9px] text-gray-400 opacity-0 group-hover:opacity-100 transition">
                  {group.owner_username}
                </span>
              )}
            </button>
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
