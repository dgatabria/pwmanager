import { useState, useEffect } from 'react'
import api from '../services/api'

interface AuthMethodConfig {
  auth_method: string
  saml_enabled: boolean
}

interface SAMLConfig {
  saml_enabled: boolean
  entity_id: string | null
  sso_url: string | null
  idp_metadata_url: string | null
  acs_url: string | null
  certificate: string | null
  entity_id_label: string | null
  slo_url: string | null
  slo_redirect_url: string | null
  certificate_label: string | null
}

export default function AdminAuthMethod() {
  const [authMethod, setAuthMethod] = useState<'local' | 'saml'>('local')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [savingSaml, setSavingSaml] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const [samlConfig, setSamlConfig] = useState<SAMLConfig>({
    saml_enabled: false,
    entity_id: null,
    sso_url: null,
    idp_metadata_url: null,
    acs_url: null,
    certificate: null,
    entity_id_label: null,
    slo_url: null,
    slo_redirect_url: null,
    certificate_label: null,
  })

  const fetchData = async () => {
    setLoading(true)
    setError('')
    setSuccess('')
    try {
      const [authData, samlData] = await Promise.all([
        api.get<AuthMethodConfig>('/admin/auth/method'),
        api.get<SAMLConfig>('/admin/auth/saml?show_secrets=true'),
      ])
      setAuthMethod(authData.auth_method as 'local' | 'saml')
      setSamlConfig(samlData)
    } catch (err: any) {
      setError(err.message || 'Failed to load authentication settings')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [])

  const handleAuthMethodChange = async (method: 'local' | 'saml') => {
    setSaving(true)
    setError('')
    setSuccess('')
    try {
      await api.put<AuthMethodConfig>('/admin/auth/method', {
        auth_method: method,
      })
      setAuthMethod(method)
      setSuccess(`Authentication method changed to ${method === 'local' ? 'Local' : 'SAML'}`)
    } catch (err: any) {
      setError(err.message || 'Failed to update authentication method')
    } finally {
      setSaving(false)
    }
  }

  const handleSamlConfigChange = async () => {
    setSavingSaml(true)
    setError('')
    setSuccess('')
    try {
      await api.put<SAMLConfig>('/admin/auth/saml', samlConfig)
      setSuccess('SAML configuration saved successfully')
    } catch (err: any) {
      setError(err.message || 'Failed to save SAML configuration')
    } finally {
      setSavingSaml(false)
    }
  }

  const isSamlEnabled = authMethod === 'saml'

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-900">Authentication Method</h1>
      </div>

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
          {error}
          <button onClick={() => setError('')} className="ml-2 font-semibold">✕</button>
        </div>
      )}

      {success && (
        <div className="p-4 bg-green-50 border border-green-200 rounded-lg text-green-700 text-sm">
          {success}
          <button onClick={() => setSuccess('')} className="ml-2 font-semibold">✕</button>
        </div>
      )}

      {loading ? (
        <div className="p-8 text-center text-gray-500">Loading...</div>
      ) : (
        <>
          {/* Authentication Method Selection */}
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Select Authentication Method</h2>
            <div className="space-y-4">
              <label className="flex items-start gap-4 p-4 border border-gray-200 rounded-lg cursor-pointer hover:bg-gray-50 transition">
                <input
                  type="radio"
                  name="authMethod"
                  checked={authMethod === 'local'}
                  onChange={() => handleAuthMethodChange('local')}
                  disabled={saving}
                  className="mt-1 w-4 h-4 text-blue-600 border-gray-300 focus:ring-blue-500"
                />
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-gray-900">Local Authentication</span>
                    {authMethod === 'local' && (
                      <span className="px-2 py-0.5 text-xs font-semibold bg-green-100 text-green-700 rounded-full">
                        Active
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-gray-500 mt-1">
                    Users authenticate with username and password stored in the local database.
                  </p>
                </div>
              </label>

              <label className="flex items-start gap-4 p-4 border border-gray-200 rounded-lg cursor-pointer hover:bg-gray-50 transition">
                <input
                  type="radio"
                  name="authMethod"
                  checked={authMethod === 'saml'}
                  onChange={() => handleAuthMethodChange('saml')}
                  disabled={saving}
                  className="mt-1 w-4 h-4 text-blue-600 border-gray-300 focus:ring-blue-500"
                />
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-gray-900">SAML</span>
                    {authMethod === 'saml' && (
                      <span className="px-2 py-0.5 text-xs font-semibold bg-green-100 text-green-700 rounded-full">
                        Active
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-gray-500 mt-1">
                    Users authenticate via SAML with an external Identity Provider (IdP).
                  </p>
                </div>
              </label>
            </div>
          </div>

          {/* SAML Configuration */}
          {isSamlEnabled && (
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-lg font-semibold text-gray-900">SAML Configuration</h2>
                <button
                  onClick={handleSamlConfigChange}
                  disabled={savingSaml}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition disabled:opacity-50 flex items-center gap-2"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  {savingSaml ? 'Saving...' : 'Save Configuration'}
                </button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Entity ID */}
                <div className="md:col-span-2">
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Entity ID
                  </label>
                  <input
                    type="text"
                    value={samlConfig.entity_id || ''}
                    onChange={(e) => setSamlConfig({ ...samlConfig, entity_id: e.target.value })}
                    placeholder="urn:example:app:sp"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                  />
                  <p className="text-xs text-gray-500 mt-1">Unique identifier for this Service Provider</p>
                </div>

                {/* SSO URL */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    SSO URL
                  </label>
                  <input
                    type="url"
                    value={samlConfig.sso_url || ''}
                    onChange={(e) => setSamlConfig({ ...samlConfig, sso_url: e.target.value })}
                    placeholder="https://idp.example.com/sso"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                  />
                  <p className="text-xs text-gray-500 mt-1">Identity Provider Single Sign-On endpoint</p>
                </div>

                {/* ACS URL */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    ACS URL
                  </label>
                  <input
                    type="url"
                    value={samlConfig.acs_url || ''}
                    onChange={(e) => setSamlConfig({ ...samlConfig, acs_url: e.target.value })}
                    placeholder="https://app.example.com/saml/acs"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                  />
                  <p className="text-xs text-gray-500 mt-1">Assertion Consumer Service endpoint</p>
                </div>

                {/* IdP Metadata URL */}
                <div className="md:col-span-2">
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    IdP Metadata URL
                  </label>
                  <input
                    type="url"
                    value={samlConfig.idp_metadata_url || ''}
                    onChange={(e) => setSamlConfig({ ...samlConfig, idp_metadata_url: e.target.value })}
                    placeholder="https://idp.example.com/metadata.xml"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                  />
                  <p className="text-xs text-gray-500 mt-1">URL to the Identity Provider metadata XML file</p>
                </div>

                {/* Certificate */}
                <div className="md:col-span-2">
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    IdP Certificate
                  </label>
                  <textarea
                    value={samlConfig.certificate || ''}
                    onChange={(e) => setSamlConfig({ ...samlConfig, certificate: e.target.value })}
                    placeholder="-----BEGIN CERTIFICATE-----&#10;MIID..."
                    rows={6}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none font-mono text-sm"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    PEM-encoded X.509 certificate from the Identity Provider for verifying SAML assertions
                  </p>
                </div>

                {/* Logout / SLO */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    SLO URL
                  </label>
                  <input
                    type="url"
                    value={samlConfig.slo_url || ''}
                    onChange={(e) => setSamlConfig({ ...samlConfig, slo_url: e.target.value })}
                    placeholder="https://idp.example.com/slo"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                  />
                  <p className="text-xs text-gray-500 mt-1">Single Logout endpoint</p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    SLO Redirect URL
                  </label>
                  <input
                    type="url"
                    value={samlConfig.slo_redirect_url || ''}
                    onChange={(e) => setSamlConfig({ ...samlConfig, slo_redirect_url: e.target.value })}
                    placeholder="https://idp.example.com/slo-redirect"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                  />
                  <p className="text-xs text-gray-500 mt-1">Single Logout redirect endpoint</p>
                </div>

                {/* Labels */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Entity ID Label
                  </label>
                  <input
                    type="text"
                    value={samlConfig.entity_id_label || ''}
                    onChange={(e) => setSamlConfig({ ...samlConfig, entity_id_label: e.target.value })}
                    placeholder="Service Provider"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Certificate Label
                  </label>
                  <input
                    type="text"
                    value={samlConfig.certificate_label || ''}
                    onChange={(e) => setSamlConfig({ ...samlConfig, certificate_label: e.target.value })}
                    placeholder="IdP Certificate"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                  />
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
