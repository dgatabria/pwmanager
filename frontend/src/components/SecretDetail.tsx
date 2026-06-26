import { useState, useEffect } from 'react'
import api from '../services/api'
import { sanitizeUrl } from '../utils/url'
import type { Secret, SecretMasked, SecretReveal, SecretCopy } from '../types'

interface Props {
  secret: Secret
  onEdit: () => void
  onDelete: () => void
}

export default function SecretDetail({ secret, onEdit, onDelete }: Props) {
  const [revealed, setRevealed] = useState(false)
  const [revealData, setRevealData] = useState<SecretReveal | null>(null)
  const [maskedData, setMaskedData] = useState<SecretMasked | null>(null)
  const [copyData, setCopyData] = useState<SecretCopy | null>(null)
  const [loading, setLoading] = useState(false)
  const [copySuccess, setCopySuccess] = useState(false)
  const [error, setError] = useState('')

  const isSSHKey = secret.secret_type === 'ssh_key'

  // Load masked data on mount
  useEffect(() => {
    loadMasked()
  }, [secret.id])

  const loadMasked = async () => {
    try {
      const data = await api.getMaskedSecret<SecretMasked>(secret.id)
      setMaskedData(data)
    } catch (err: any) {
      setError(err.message)
    }
  }

  const handleReveal = async () => {
    setLoading(true)
    setError('')
    try {
      const data = await api.revealSecret<SecretReveal>(secret.id)
      setRevealData(data)
      setRevealed(true)
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleCopy = async () => {
    setLoading(true)
    setError('')
    try {
      const data = await api.copySecret<SecretCopy>(secret.id)
      setCopyData(data)

      // Copy to clipboard
      await navigator.clipboard.writeText(data.decrypted_data)
      setCopySuccess(true)
      setTimeout(() => setCopySuccess(false), 2000)
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleCopyUsername = async () => {
    if (secret.username) {
      try {
        await navigator.clipboard.writeText(secret.username)
        setCopySuccess(true)
        setTimeout(() => setCopySuccess(false), 2000)
      } catch {
        // ignore
      }
    }
  }

  const displayData = revealed && revealData ? revealData.decrypted_data : (maskedData?.decrypted_data || '••••••••••••••••')

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
            <button
              onClick={handleCopyUsername}
              className="text-sm font-medium mt-1 flex items-center gap-1 hover:text-blue-600 transition"
            >
              {secret.username}
              <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
            </button>
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
            {(() => {
              const safeUrl = sanitizeUrl(secret.url)
              if (!safeUrl) {
                return (
                  <p className="text-sm text-red-500 mt-1">Invalid URL (protocol not allowed)</p>
                )
              }
              return (
                <a href={safeUrl} target="_blank" rel="noopener noreferrer" className="text-sm text-blue-600 hover:underline mt-1 block">
                  {safeUrl}
                </a>
              )
            })()}
          </div>
        )}
      </div>

      {/* Secret data */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <div className="px-4 py-3 bg-gray-50 border-b border-gray-200 flex justify-between items-center">
          <span className="text-sm font-medium text-gray-700">
            {isSSHKey ? 'Private Key' : 'Secret Value'}
          </span>
          <div className="flex gap-2">
            <button
              onClick={handleReveal}
              disabled={loading}
              className="text-xs bg-amber-500 text-white px-3 py-1.5 rounded-lg hover:bg-amber-600 transition flex items-center gap-1 disabled:opacity-50"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
              </svg>
              Reveal
            </button>
            <button
              onClick={handleCopy}
              disabled={loading}
              className="text-xs bg-blue-600 text-white px-3 py-1.5 rounded-lg hover:bg-blue-700 transition flex items-center gap-1 disabled:opacity-50"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
              {copySuccess ? '✓ Copied!' : 'Copy To Clipboard'}
            </button>
          </div>
        </div>
        <div className="p-4">
          <pre className="text-sm font-mono p-4 rounded-lg overflow-auto max-h-96 whitespace-pre-wrap break-all">
            {revealed ? (
              <code className="bg-gray-900 text-green-400 block">{displayData}</code>
            ) : (
              <div className="bg-gray-100 text-gray-400 p-4 rounded-lg text-center">
                <div className="flex flex-col items-center gap-2">
                  <svg className="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                  </svg>
                  <p className="text-sm font-medium">Hidden for security</p>
                  <p className="text-xs text-gray-500">Click "Reveal" to view this secret</p>
                  <p className="text-xs text-gray-400 mt-2">••••••••••••••••</p>
                </div>
              </div>
            )}
          </pre>
        </div>
      </div>

      {/* Audit info - shown after reveal */}
      {revealed && revealData && (
        <div className="mt-4 bg-amber-50 border border-amber-200 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            <svg className="w-4 h-4 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
            <span className="text-sm font-medium text-amber-800">Audit Trail</span>
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div>
              <span className="text-amber-600">Event:</span>{' '}
              <span className="text-amber-700 font-mono">{revealData.audit_event}</span>
            </div>
            <div>
              <span className="text-amber-600">Audit ID:</span>{' '}
              <span className="text-amber-700 font-mono">#{revealData.audit_id}</span>
            </div>
            <div>
              <span className="text-amber-600">IP Address:</span>{' '}
              <span className="text-amber-700 font-mono">{revealData.audit_ip}</span>
            </div>
            <div>
              <span className="text-amber-600">Timestamp:</span>{' '}
              <span className="text-amber-700 font-mono">{new Date(revealData.audit_timestamp).toLocaleString()}</span>
            </div>
          </div>
        </div>
      )}

      {/* Copy success indicator */}
      {copySuccess && (
        <div className="mt-2 bg-green-50 border border-green-200 rounded-lg p-3 text-green-700 text-sm text-center">
          ✓ Copied to clipboard successfully
        </div>
      )}

      {/* Copy audit info */}
      {copyData && (
        <div className="mt-2 bg-blue-50 border border-blue-200 rounded-lg p-3">
          <div className="flex items-center gap-2 mb-1">
            <svg className="w-4 h-4 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
            </svg>
            <span className="text-sm font-medium text-blue-800">Copy Audit</span>
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div>
              <span className="text-blue-600">Event:</span>{' '}
              <span className="text-blue-700 font-mono">{copyData.audit_event}</span>
            </div>
            <div>
              <span className="text-blue-600">Audit ID:</span>{' '}
              <span className="text-blue-700 font-mono">#{copyData.audit_id}</span>
            </div>
            <div>
              <span className="text-blue-600">IP Address:</span>{' '}
              <span className="text-blue-700 font-mono">{copyData.audit_ip}</span>
            </div>
            <div>
              <span className="text-blue-600">Timestamp:</span>{' '}
              <span className="text-blue-700 font-mono">{new Date(copyData.audit_timestamp).toLocaleString()}</span>
            </div>
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm">
          {error}
        </div>
      )}

      {/* Timestamps */}
      <div className="mt-6 text-xs text-gray-400 flex gap-4">
        <span>Created: {new Date(secret.created_at).toLocaleString()}</span>
        <span>Updated: {new Date(secret.updated_at).toLocaleString()}</span>
      </div>
    </div>
  )
}
