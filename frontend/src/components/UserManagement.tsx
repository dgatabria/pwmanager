import { useState } from 'react'
import type { Group } from '../types'

interface Props {
  groups: Group[]
  onRefresh: () => void
}

export default function UserManagement({ groups, onRefresh }: Props) {
  const [activeSection, setActiveSection] = useState<'groups' | 'users'>('groups')
  const [newGroupName, setNewGroupName] = useState('')

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">User & Group Management</h1>

      <div className="flex gap-2">
        <button
          onClick={() => setActiveSection('groups')}
          className={`px-4 py-2 rounded-lg font-medium transition ${
            activeSection === 'groups' ? 'bg-blue-600 text-white' : 'bg-white text-gray-700 hover:bg-gray-100'
          }`}
        >
          Groups
        </button>
        <button
          onClick={() => setActiveSection('users')}
          className={`px-4 py-2 rounded-lg font-medium transition ${
            activeSection === 'users' ? 'bg-blue-600 text-white' : 'bg-white text-gray-700 hover:bg-gray-100'
          }`}
        >
          Users
        </button>
      </div>

      {activeSection === 'groups' && (
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Groups</h2>
          <p className="text-sm text-gray-500 mb-4">
            Groups are used for RBAC. Assign users to groups and grant groups access to secret groups.
          </p>

          {groups.length === 0 ? (
            <p className="text-gray-400 text-sm">No groups configured.</p>
          ) : (
            <div className="space-y-3">
              {groups.map((group) => (
                <div
                  key={group.id}
                  className="flex items-center justify-between p-4 bg-gray-50 rounded-lg"
                >
                  <div>
                    <h3 className="font-medium text-gray-900">{group.name}</h3>
                    {group.description && (
                      <p className="text-sm text-gray-500">{group.description}</p>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded-full">
                      {group.user_ids?.length || 0} users
                    </span>
                    <span className={`text-xs px-2 py-1 rounded-full ${group.is_active ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                      {group.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {activeSection === 'users' && (
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Users</h2>
          <p className="text-sm text-gray-500 mb-4">
            Manage users and assign them to groups for access control.
          </p>
          <div className="p-8 text-center text-gray-400">
            <p>User management is available via the API.</p>
            <code className="text-xs bg-gray-100 px-2 py-1 rounded mt-2 inline-block">
              POST /api/users
            </code>
          </div>
        </div>
      )}
    </div>
  )
}
