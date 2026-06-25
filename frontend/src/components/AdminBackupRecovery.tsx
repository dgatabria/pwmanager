import { useState, useEffect } from 'react'
import api from '../services/api'

interface BackupStatus {
  user_count: number
  group_count: number
  status: string
  message: string
}

interface BackupInfo {
  message: string
  timestamp?: string
  user_id?: number
  backup_type?: string
  status?: string
  backup_id?: string
}

interface RotationResult {
  message: string
  secrets_processed: number
  secrets_failed: number
  total_secrets: number
  status: string
  timestamp?: string
}

interface BackupListResponse {
  backups: any[]
  message: string
}

export default function AdminBackupRecovery() {
  const [status, setStatus] = useState<BackupStatus | null>(null)
  const [backups, setBackups] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [executing, setExecuting] = useState(false)
  const [restoring, setRestoring] = useState(false)
  const [rotating, setRotating] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [showRestoreModal, setShowRestoreModal] = useState(false)
  const [backupIdToRestore, setBackupIdToRestore] = useState('')
  const [showRotationModal, setShowRotationModal] = useState(false)
  const [rotationResult, setRotationResult] = useState<RotationResult | null>(null)

  const fetchData = async () => {
    setLoading(true)
    setError('')
    setSuccess('')
    try {
      const [statusData, backupsData] = await Promise.all([
        api.get<BackupStatus>('/admin/backup/status'),
        api.get<BackupListResponse>('/admin/backup/list'),
      ])
      setStatus(statusData)
      setBackups(backupsData.backups || [])
    } catch (err: any) {
      setError(err.message || 'Failed to load backup status')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [])

  const handleExecuteBackup = async () => {
    if (!confirm('Execute full database backup? This may take a few moments.')) return
    setExecuting(true)
    setError('')
    setSuccess('')
    try {
      const result = await api.post<BackupInfo>('/admin/backup/execute', {})
      setSuccess(result.message || 'Backup executed successfully')
      await fetchData()
    } catch (err: any) {
      setError(err.message || 'Failed to execute backup')
    } finally {
      setExecuting(false)
    }
  }

  const handleRestore = async () => {
    if (!backupIdToRestore) {
      setError('Please enter a backup ID')
      return
    }
    if (!confirm('⚠️ WARNING: This will overwrite ALL current database data. Are you absolutely sure?')) return
    setRestoring(true)
    setError('')
    setSuccess('')
    try {
      const result = await api.post<BackupInfo>(`/admin/backup/${backupIdToRestore}/restore`, {})
      setSuccess(result.message || 'Restore executed successfully')
      setShowRestoreModal(false)
      setBackupIdToRestore('')
      await fetchData()
    } catch (err: any) {
      setError(err.message || 'Failed to restore backup')
    } finally {
      setRestoring(false)
    }
  }

  const handleRotateKey = async () => {
    if (!confirm('⚠️ WARNING: This will put the application in maintenance mode and re-encrypt all secrets. This may take several minutes. Continue?')) return
    setRotating(true)
    setError('')
    setSuccess('')
    setRotationResult(null)
    try {
      const result = await api.post<RotationResult>('/admin/secrets/rotate-key', {})
      setRotationResult(result)
      setSuccess(result.message || 'Key rotation executed successfully')
      await fetchData()
    } catch (err: any) {
      setError(err.message || 'Failed to rotate key')
    } finally {
      setRotating(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-900">Mantenimiento</h1>
        <button
          onClick={fetchData}
          className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition flex items-center gap-2"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          Refresh
        </button>
      </div>

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
          {error}
        </div>
      )}

      {success && (
        <div className="p-4 bg-green-50 border border-green-200 rounded-lg text-green-700 text-sm">
          {success}
        </div>
      )}

      {/* Database Stats */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <div className="text-sm text-gray-500 mb-1">Total Users</div>
          <div className="text-3xl font-bold text-gray-900">
            {loading ? '...' : status?.user_count || 0}
          </div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <div className="text-sm text-gray-500 mb-1">Total Groups</div>
          <div className="text-3xl font-bold text-gray-900">
            {loading ? '...' : status?.group_count || 0}
          </div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <div className="text-sm text-gray-500 mb-1">Status</div>
          <div className="text-3xl font-bold text-green-600">
            {loading ? '...' : status?.status || 'Unknown'}
          </div>
        </div>
      </div>

      {/* Backup Actions */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Backup Operations</h2>
        
        <div className="space-y-4">
          <div className="flex items-start gap-4 p-4 bg-blue-50 rounded-lg">
            <svg className="w-6 h-6 text-blue-600 mt-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
            <div className="flex-1">
              <h3 className="font-medium text-blue-900">Execute Full Backup</h3>
              <p className="text-sm text-blue-700 mt-1">
                Create a complete backup of the database. This operation may take several minutes depending on database size.
              </p>
              <button
                onClick={handleExecuteBackup}
                disabled={executing}
                className="mt-3 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition disabled:opacity-50"
              >
                {executing ? 'Backing up...' : 'Execute Backup'}
              </button>
            </div>
          </div>

          <div className="flex items-start gap-4 p-4 bg-amber-50 rounded-lg">
            <svg className="w-6 h-6 text-amber-600 mt-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <div className="flex-1">
              <h3 className="font-medium text-amber-900">Restore from Backup</h3>
              <p className="text-sm text-amber-700 mt-1">
                ⚠️ WARNING: This will overwrite ALL current database data. Use with extreme caution.
              </p>
              <button
                onClick={() => setShowRestoreModal(true)}
                disabled={restoring || backups.length === 0}
                className="mt-3 px-4 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-700 transition disabled:opacity-50"
              >
                {restoring ? 'Restoring...' : 'Restore Backup'}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Encryption Key Rotation */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Encryption Key Management</h2>
        
        <div className="space-y-4">
          <div className="flex items-start gap-4 p-4 bg-purple-50 rounded-lg">
            <svg className="w-6 h-6 text-purple-600 mt-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.227-2.573 4.018-2.007 2.46.677 3.138 3.868 1.386 5.62-.778.778-1.266 1.81-1.266 2.896 0 2.762 2.238 5 5 5 .902 0 1.734-.302 2.396-.806 1.752-1.752 1.074-4.943-1.386-5.62-1.792-.546-3.593.249-4.018 2.007-.294 1.21.058 2.363.768 3.217" />
            </svg>
            <div className="flex-1">
              <h3 className="font-medium text-purple-900">Rotate Encryption Key</h3>
              <p className="text-sm text-purple-700 mt-1">
                Generate a new encryption key and re-encrypt all secrets. This will put the application in maintenance mode temporarily.
              </p>
              <button
                onClick={() => setShowRotationModal(true)}
                disabled={rotating}
                className="mt-3 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition disabled:opacity-50"
              >
                {rotating ? 'Rotating...' : 'Rotate Encryption Key'}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Backup List */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Available Backups</h2>
        {backups.length === 0 ? (
          <div className="p-8 text-center text-gray-400">
            <svg className="w-12 h-12 mx-auto mb-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4" />
            </svg>
            <p>No backups available. Execute a backup first.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {backups.map((backup, index) => (
              <div key={index} className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                <div>
                  <div className="font-medium text-gray-900">Backup #{index + 1}</div>
                  <div className="text-sm text-gray-500">
                    {backup.timestamp ? new Date(backup.timestamp).toLocaleString() : 'Unknown date'}
                  </div>
                </div>
                <button
                  onClick={() => {
                    setBackupIdToRestore(backup.id || `backup_${index}`)
                    setShowRestoreModal(true)
                  }}
                  className="px-4 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-700 text-sm"
                >
                  Restore
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Restore Confirmation Modal */}
      {showRestoreModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg m-4 p-6">
            <div className="flex items-center gap-3 mb-4">
              <svg className="w-8 h-8 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <h2 className="text-xl font-bold text-gray-900">Confirm Restore</h2>
            </div>
            <div className="p-4 bg-red-50 border border-red-200 rounded-lg mb-4">
              <p className="text-sm text-red-800 font-medium">
                ⚠️ This action is irreversible. All current data will be permanently replaced.
              </p>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Backup ID to Restore</label>
                <input
                  type="text"
                  value={backupIdToRestore}
                  onChange={(e) => setBackupIdToRestore(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 outline-none"
                  placeholder="Enter backup ID"
                />
              </div>
              <div className="flex justify-end gap-3">
                <button
                  onClick={() => {
                    setShowRestoreModal(false)
                    setBackupIdToRestore('')
                  }}
                  className="px-4 py-2 text-sm text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200"
                >
                  Cancel
                </button>
                <button
                  onClick={handleRestore}
                  className="px-4 py-2 text-sm text-white bg-red-600 rounded-lg hover:bg-red-700"
                >
                  Confirm Restore
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Rotation Confirmation Modal */}
      {showRotationModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg m-4 p-6">
            <div className="flex items-center gap-3 mb-4">
              <svg className="w-8 h-8 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.227-2.573 4.018-2.007 2.46.677 3.138 3.868 1.386 5.62-.778.778-1.266 1.81-1.266 2.896 0 2.762 2.238 5 5 5 .902 0 1.734-.302 2.396-.806 1.752-1.752 1.074-4.943-1.386-5.62-1.792-.546-3.593.249-4.018 2.007-.294 1.21.058 2.363.768 3.217" />
              </svg>
              <h2 className="text-xl font-bold text-gray-900">Confirm Key Rotation</h2>
            </div>
            <div className="p-4 bg-purple-50 border border-purple-200 rounded-lg mb-4">
              <p className="text-sm text-purple-800 font-medium">
                ⚠️ This will put the application in maintenance mode and re-encrypt all secrets. Non-admin users will be locked out during this process. This may take several minutes.
              </p>
            </div>
            <div className="space-y-4">
              <div className="p-3 bg-gray-50 rounded-lg">
                <p className="text-sm text-gray-600">
                  <strong>What happens:</strong>
                </p>
                <ul className="text-sm text-gray-600 mt-1 list-disc list-inside space-y-1">
                  <li>Maintenance mode is activated</li>
                  <li>All secrets are decrypted with the old key</li>
                  <li>Secrets are re-encrypted with a new key</li>
                  <li>The new key is saved to disk</li>
                  <li>Maintenance mode is deactivated</li>
                </ul>
              </div>
              <div className="flex justify-end gap-3">
                <button
                  onClick={() => setShowRotationModal(false)}
                  className="px-4 py-2 text-sm text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200"
                >
                  Cancel
                </button>
                <button
                  onClick={handleRotateKey}
                  className="px-4 py-2 text-sm text-white bg-purple-600 rounded-lg hover:bg-purple-700"
                >
                  Start Rotation
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Rotation Result Modal */}
      {rotationResult && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg m-4 p-6">
            <div className="flex items-center gap-3 mb-4">
              <svg className="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <h2 className="text-xl font-bold text-gray-900">Key Rotation Complete</h2>
            </div>
            <div className="space-y-4">
              <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
                <p className="text-sm text-green-800 font-medium">{rotationResult.message}</p>
              </div>
              <div className="grid grid-cols-3 gap-4">
                <div className="text-center p-3 bg-gray-50 rounded-lg">
                  <div className="text-2xl font-bold text-gray-900">{rotationResult.secrets_processed}</div>
                  <div className="text-sm text-gray-500">Processed</div>
                </div>
                <div className="text-center p-3 bg-gray-50 rounded-lg">
                  <div className="text-2xl font-bold text-gray-900">{rotationResult.secrets_failed}</div>
                  <div className="text-sm text-gray-500">Failed</div>
                </div>
                <div className="text-center p-3 bg-gray-50 rounded-lg">
                  <div className="text-2xl font-bold text-gray-900">{rotationResult.total_secrets}</div>
                  <div className="text-sm text-gray-500">Total</div>
                </div>
              </div>
              {rotationResult.timestamp && (
                <p className="text-xs text-gray-500 text-center">
                  Completed at: {new Date(rotationResult.timestamp).toLocaleString()}
                </p>
              )}
              <div className="flex justify-end">
                <button
                  onClick={() => {
                    setShowRotationModal(false)
                    setRotationResult(null)
                  }}
                  className="px-4 py-2 text-sm text-white bg-purple-600 rounded-lg hover:bg-purple-700"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
