import { useState, useEffect, useCallback } from 'react'
import api from '../services/api'
import type { AuditLog, AuditLogList } from '../types'

export default function AuditLogs() {
  const [logs, setLogs] = useState<AuditLog[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [eventFilter, setEventFilter] = useState('')
  const [userIdFilter, setUserIdFilter] = useState('')
  const [secretIdFilter, setSecretIdFilter] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize] = useState(50)
  const [totalPages, setTotalPages] = useState(1)
  const [total, setTotal] = useState(0)

  const fetchLogs = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const params: Record<string, string | number> = { page, page_size: pageSize }
      if (eventFilter) params.event_type = eventFilter
      if (userIdFilter) params.user_id = Number(userIdFilter)
      if (secretIdFilter) params.secret_id = Number(secretIdFilter)
      if (search) params.search = search

      const data = await api.getAuditLogs<AuditLogList>(params)
      setLogs(data.logs)
      setTotalPages(data.total_pages)
      setTotal(data.total)
    } catch (err: any) {
      setError(err.message || 'Failed to load audit logs')
    } finally {
      setLoading(false)
    }
  }, [page, pageSize, eventFilter, userIdFilter, secretIdFilter, search])

  useEffect(() => {
    fetchLogs()
  }, [fetchLogs])

  const handleSearch = () => {
    setPage(1)
    fetchLogs()
  }

  const handlePageChange = (newPage: number) => {
    setPage(newPage)
  }

  const clearFilters = () => {
    setSearch('')
    setEventFilter('')
    setUserIdFilter('')
    setSecretIdFilter('')
    setPage(1)
  }

  const getEventBadgeColor = (event: string) => {
    if (event.includes('reveal')) return 'bg-amber-100 text-amber-700'
    if (event.includes('copy')) return 'bg-blue-100 text-blue-700'
    if (event.includes('view')) return 'bg-purple-100 text-purple-700'
    if (event.includes('delete')) return 'bg-red-100 text-red-700'
    if (event.includes('create')) return 'bg-green-100 text-green-700'
    if (event.includes('update')) return 'bg-yellow-100 text-yellow-700'
    return 'bg-gray-100 text-gray-700'
  }

  const formatTimestamp = (ts: string | null) => {
    if (!ts) return '—'
    return new Date(ts).toLocaleString()
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-900">Audit Logs</h1>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-3">
          <input
            type="text"
            placeholder="Search details..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm"
          />
          <select
            value={eventFilter}
            onChange={(e) => { setEventFilter(e.target.value); setPage(1) }}
            className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm"
          >
            <option value="">All event types</option>
            <option value="secret_reveal">Secret Reveal</option>
            <option value="secret_copy">Secret Copy</option>
            <option value="secret_view">Secret View</option>
            <option value="secret_delete">Secret Delete</option>
            <option value="user_create">User Create</option>
            <option value="user_update">User Update</option>
            <option value="user_delete">User Delete</option>
            <option value="api_token_create">API Token Create</option>
            <option value="ssh_key_generate">SSH Key Generate</option>
          </select>
          <input
            type="number"
            placeholder="User ID"
            value={userIdFilter}
            onChange={(e) => { setUserIdFilter(e.target.value); setPage(1) }}
            className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm"
          />
          <input
            type="number"
            placeholder="Secret ID"
            value={secretIdFilter}
            onChange={(e) => { setSecretIdFilter(e.target.value); setPage(1) }}
            className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm"
          />
          <div className="flex gap-2">
            <button
              onClick={handleSearch}
              className="flex-1 px-3 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
            >
              Search
            </button>
            <button
              onClick={clearFilters}
              className="px-3 py-2 text-sm bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition"
            >
              Clear
            </button>
          </div>
        </div>
      </div>

      {/* Summary */}
      <div className="text-sm text-gray-500">
        Showing <span className="font-medium text-gray-700">{logs.length}</span> of{' '}
        <span className="font-medium text-gray-700">{total}</span> audit logs
        {totalPages > 1 && (
          <span className="ml-2">— Page {page} of {totalPages}</span>
        )}
      </div>

      {/* Table */}
      {loading ? (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8 text-center text-gray-500">
          Loading audit logs...
        </div>
      ) : error ? (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-red-600 text-sm">
          {error}
        </div>
      ) : logs.length === 0 ? (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8 text-center text-gray-500">
          No audit logs found matching the current filters.
        </div>
      ) : (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">ID</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">User</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Event</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Secret</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">IP Address</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Timestamp</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {logs.map((log) => (
                  <tr key={log.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm font-mono text-gray-600">#{log.id}</td>
                    <td className="px-4 py-3 text-sm">
                      {log.user_username ? (
                        <span className="text-gray-900 font-medium">{log.user_username}</span>
                      ) : (
                        <span className="text-gray-400">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm">
                      <span className={`inline-block px-2 py-1 text-xs font-medium rounded-full ${getEventBadgeColor(log.event_type)}`}>
                        {log.event_type}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {log.secret_title ? (
                        <span>#{log.secret_id} — {log.secret_title}</span>
                      ) : (
                        <span className="text-gray-400">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm font-mono text-gray-600">
                      {log.ip_address || '—'}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600 whitespace-nowrap">
                      {formatTimestamp(log.timestamp)}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500 max-w-xs truncate">
                      {log.details || '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between bg-white rounded-xl shadow-sm border border-gray-200 px-4 py-3">
          <span className="text-sm text-gray-600">
            Page {page} of {totalPages}
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => handlePageChange(page - 1)}
              disabled={page <= 1}
              className="px-3 py-1.5 text-sm bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition"
            >
              ← Previous
            </button>
            <button
              onClick={() => handlePageChange(page + 1)}
              disabled={page >= totalPages}
              className="px-3 py-1.5 text-sm bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition"
            >
              Next →
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
