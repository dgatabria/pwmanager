import type { SecretGroup, Group } from '../types'

interface Props {
  groups: SecretGroup[]
  userGroups: Group[]
  selectedGroupId: number | null
  onSelectGroup: (id: number | null) => void
  onAddGroup: () => void
}

export default function GroupSidebar({ groups, userGroups, selectedGroupId, onSelectGroup }: Props) {
  return (
    <div className="w-56 bg-white border-r border-gray-200 flex flex-col shrink-0 overflow-y-auto">
      <div className="p-3 border-b border-gray-200">
        <h2 className="text-xs font-bold text-gray-500 uppercase tracking-wider">Secret Groups</h2>
      </div>

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

      <div className="px-2 pb-2">
        <div className="text-xs text-gray-400 uppercase tracking-wider px-3 py-1">Groups</div>
        {groups.map((group) => (
          <button
            key={group.id}
            onClick={() => onSelectGroup(group.id)}
            className={`w-full text-left px-3 py-2 rounded-lg text-sm transition ${
              selectedGroupId === group.id
                ? 'bg-blue-50 text-blue-700 font-medium'
                : 'text-gray-600 hover:bg-gray-50'
            }`}
          >
            {group.name}
          </button>
        ))}
      </div>

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
