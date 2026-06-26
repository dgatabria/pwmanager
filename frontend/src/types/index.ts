export type SecretType = 'ssh_key' | 'password' | 'credential' | 'api_key' | 'custom'
export type GroupPermission = 'read' | 'write'

export interface Secret {
  id: number
  title: string
  description: string | null
  secret_type: SecretType
  decrypted_data: string | null
  key_length: number | null
  username: string | null
  url: string | null
  group_id: number
  owner_id: number
  is_active: boolean
  created_at: string
  updated_at: string
  group_name?: string
  owner_username?: string
}

export interface SecretMasked {
  id: number
  title: string
  description: string | null
  secret_type: SecretType
  decrypted_data: string // always "••••••••••••••••"
  key_length: number | null
  username: string | null
  url: string | null
  group_name: string | null
  owner_username: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface SecretReveal {
  id: number
  title: string
  description: string | null
  secret_type: SecretType
  decrypted_data: string
  key_length: number | null
  username: string | null
  url: string | null
  group_name: string | null
  owner_username: string | null
  is_active: boolean
  created_at: string
  updated_at: string
  audit_id: number
  audit_event: string
  audit_timestamp: string
  audit_ip: string
}

export interface SecretCopy {
  id: number
  title: string
  decrypted_data: string
  audit_id: number
  audit_event: string
  audit_timestamp: string
  audit_ip: string
}

export interface APIToken {
  id: number
  name: string
  description: string | null
  is_active: boolean
  created_at: string
  last_used_at: string | null
  expires_at: string | null
}

export interface APITokenCreateResponse {
  token: string
  token_id: number
  name: string
  description: string | null
  created_at: string
  expires_at: string | null
  warning: string
}

export interface APITokenRecycleResponse {
  new_token: string
  warning: string
}

export interface APITokenRevokeResponse {
  message: string
  revoked_token_id: number
}

export interface SecretGroup {
  id: number
  name: string
  description: string | null
  parent_id: number | null
  group_id: number | null
  owner_id: number
  user_id: number | null
  is_personal: boolean
  owner_username?: string
  is_active: boolean
  group_ids?: number[]
  child_count?: number
  secret_count?: number
  children?: SecretGroup[]
}

export interface User {
  id: number
  username: string
  email: string
  full_name: string | null
  is_active: boolean
  is_superuser: boolean
  created_at: string
}

export interface Group {
  id: number
  name: string
  description: string | null
  is_active: boolean
  user_ids?: number[]
}

export interface LoginRequest {
  username: string
  password: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
}

export interface AuditLog {
  id: number
  user_id: number | null
  user_username: string | null
  event_type: string
  secret_id: number | null
  secret_title: string | null
  ip_address: string | null
  user_agent: string | null
  details: string | null
  timestamp: string | null
}

export interface AuditLogList {
  logs: AuditLog[]
  total: number
  page: number
  page_size: number
  total_pages: number
}
