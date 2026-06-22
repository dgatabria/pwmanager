# 🔒 Security Audit Report — Password Manager (ia-tests-2)

> **Scope**: Full codebase scan (backend Python/FastAPI + frontend React/Vite + Docker Compose)
> **Date**: 2026-06-22
> **Severity**: Critical → High → Medium → Low

---

## 🔴 CRITICAL

### 1. Hardcoded Credentials & Default Secrets

| File | Line | Issue |
|------|------|-------|
| `backend/seed.py` | 35 | Admin password hardcoded as `Admin@123` |
| `backend/.env.example` | 1 | Default DB credentials `postgres:postgres` |
| `docker-compose.yml` | 7, 24 | DB password `postgres` hardcoded in env vars |
| `backend/app/config.py` | 11, 12, 15 | Default `SECRET_KEY`, `ENCRYPTION_KEY`, `DATABASE_URL` are all placeholder values |

**Impact**: Anyone who reads the source code or the Docker Compose file can access the database, log in as admin, or decrypt all stored secrets.

**Fix**:
- Remove hardcoded password from `seed.py`; generate a random one at first-run and store it securely
- Use Docker secrets or a `.env` file (git-ignored) for all credentials
- Never commit `.env` files or templates with real passwords

---

### 2. JWT Authentication Bypass — HS256 with Well-Known Key

| File | Line | Issue |
|------|------|-------|
| `backend/app/config.py` | 13 | `ALGORITHM = "HS256"` |
| `backend/app/config.py` | 12 | `SECRET_KEY = "change-this-to-a-secure-random-string-in-production"` |
| `backend/app/services/auth.py` | 21 | `jwt.encode(..., settings.SECRET_KEY, algorithm=settings.ALGORITHM)` |

**Impact**: HS256 requires the same secret for signing and verification. With a well-known default key, any attacker can:
- Forge arbitrary JWT tokens (e.g., `{"sub": "1", "exp": ...}`) to authenticate as admin
- Bypass all authentication without knowing any real password

**Fix**:
- Switch to `RS256` (asymmetric) or at minimum generate a cryptographically random 256-bit secret on first run
- Enforce that the key is NOT the default placeholder before starting the server

---

### 3. Authorization Bypass — Unauthenticated Privilege Escalation via `/api/users`

| File | Line | Issue |
|------|------|-------|
| `backend/app/routers/groups.py` | 26-42 | `GET /api/users` — any auth'd user can list ALL users |
| `backend/app/routers/groups.py` | 45-102 | `POST /api/users` — any auth'd user can create users |
| `backend/app/routers/groups.py` | 105-137 | `PUT /api/users/{user_id}` — any auth'd user can modify ANY user's email, active status |
| `backend/app/routers/groups.py` | 140-177 | `POST/DELETE /api/users/{user_id}/groups/{group_id}` — any auth'd user can add/remove users from groups |
| `backend/app/routers/groups.py` | 182-297 | `POST/PUT/DELETE /api/groups/{group_id}` — any auth'd user can manage groups |

**Impact**: Any authenticated user (even non-admin) can:
- Enumerate all users and their emails
- Create new user accounts
- Modify any user's email or deactivate any account
- Add/remove users from any group
- Create, update, and delete groups entirely

Note: There is already an `admin.py` router with `require_superuser()` — but the `groups.py` router provides an **unprotected parallel API** that bypasses all of it.

**Fix**:
- Add `require_superuser()` checks to all user/group management endpoints in `groups.py`, or
- Remove the unprotected endpoints in `groups.py` and only use the admin router

---

### 4. User Enumeration — Full User Directory Exposed

| File | Line | Issue |
|------|------|-------|
| `backend/app/routers/groups.py` | 26-42 | `GET /api/users` returns all users with emails, names, superuser status |

**Impact**: Any authenticated user can enumerate every user in the system, including their email addresses, full names, and admin status. This aids phishing and targeted attacks.

**Fix**: Restrict user listing to superusers only (use `require_superuser()`).

---

## 🟠 HIGH

### 5. Missing Rate Limiting on Sensitive Endpoints

| File | Line | Issue |
|------|------|-------|
| `backend/app/routers/admin.py` | 184 | `POST /api/admin/users/{user_id}/reset-password` — **NO rate limit** |
| `backend/app/routers/api_tokens.py` | 98 | `POST /api/api-tokens/generate` — **NO rate limit** |
| `backend/app/routers/secrets.py` | 364 | `GET /secrets/{id}/reveal` — **NO rate limit** |
| `backend/app/routers/secrets.py` | 415 | `POST /secrets/{id}/copy` — **NO rate limit** |

**Impact**:
- Password reset can be abused for brute-force attacks
- API tokens can be generated endlessly
- Secrets can be revealed/copied at unlimited speed, exfiltrating data

**Fix**: Apply `@limiter.limit()` decorators to all sensitive endpoints (e.g., `5/minute`).

---

### 6. Encryption Key Lost on Restart — Secrets Become Unrecoverable

| File | Line | Issue |
|------|------|-------|
| `backend/app/services/encryption.py` | 18-21 | When `ENCRYPTION_KEY` is the default placeholder, a random key is generated at runtime and stored in `settings.ENCRYPTION_KEY` |

**Impact**: If the placeholder key is not overridden in production, a new random key is generated on every server restart. All previously encrypted secrets become **permanently unreadable**.

**Fix**:
- Reject the default placeholder value at startup and refuse to start
- Store the generated key persistently (e.g., in a config file or env var)

---

### 7. Sensitive Data Exposed in Secret List Response

| File | Line | Issue |
|------|------|-------|
| `backend/app/routers/secrets.py` | 111-154 | `GET /api/secrets` returns `username` field for every secret |

**Impact**: The list endpoint returns the `username` associated with each secret (e.g., database usernames, API user names). This could be sensitive information that should only be revealed on-demand.

**Fix**: Remove `username` from the list response or mask it.

---

### 8. SAML Certificate Stored in Memory Without Encryption

| File | Line | Issue |
|------|------|-------|
| `backend/app/routers/admin.py` | 435-446 | `_saml_config` dict stores `certificate` and `certificate_label` in plain text in memory |

**Impact**: SAML certificates and private key references are stored in an in-memory dict that is lost on restart. If the server is restarted, configuration is lost. There's no persistence layer, and the certificate data is not encrypted.

**Fix**: Store SAML config in the database with encryption at rest.

---

### 9. No Input Validation on SSH Key Generation

| File | Line | Issue |
|------|------|-------|
| `backend/app/routers/secrets.py` | 311-328 | `POST /api/secrets/ssh-key/generate` accepts `key_length` with no bounds checking |

**Impact**: An attacker could request extremely large keys (e.g., `key_length=100000`) causing:
- CPU exhaustion (DoS)
- Memory exhaustion
- Potential service disruption

**Fix**: Validate `key_length` is within a reasonable range (e.g., 2048–8192).

---

### 10. Client-Side JWT Decoding Without Server-Side Verification

| File | Line | Issue |
|------|------|-------|
| `frontend/src/contexts/AuthContext.tsx` | 28-40 | `atob()` decodes JWT payload client-side to extract user info without server-side verification |

**Impact**: The frontend trusts the JWT payload to determine `isSuperuser`. An attacker can forge a client-side token with `is_superuser: true` to access the admin dashboard UI. While the backend still validates the JWT signature, the client-side role check is bypassable.

**Fix**: Always rely on server-side role information (e.g., fetch `/me` and trust the server response).

---

## 🟡 MEDIUM

### 11. Weak Password Policy

| File | Line | Issue |
|------|------|-------|
| `frontend/src/components/AdminUserManagement.tsx` | 80 | `newPassword.length < 8` — minimum 8 characters, no complexity requirements |

**Impact**: Weak passwords like `12345678` or `aaaaaaaa` are accepted. No minimum length for complexity, no banned common passwords, no uppercase/lowercase/number/special character requirements.

**Fix**: Enforce a minimum of 12 characters with complexity requirements, and check against a list of common passwords.

---

### 12. IP Address Spoofing in Audit Logs

| File | Line | Issue |
|------|------|-------|
| `backend/app/services/audit.py` | 22-25 | `x-forwarded-for` header is trusted without validation |

**Impact**: An attacker can set `X-Forwarded-For: <attacker_ip>` to spoof their IP address in audit logs, evading detection.

**Fix**: Only trust `X-Forwarded-For` when the request comes from a known reverse proxy IP. Otherwise, use the direct connection IP.

---

### 13. CORS with `allow_credentials=True` and User-Configurable Origins

| File | Line | Issue |
|------|------|-------|
| `backend/app/main.py` | 46-52 | `allow_credentials=True` with origins from `ALLOWED_ORIGINS` env var |

**Impact**: If `ALLOWED_ORIGINS` is misconfigured (e.g., `*` or an attacker-controlled origin), credentials (cookies, auth headers) are sent to that origin. While the current code doesn't use cookies, the `Authorization` header is sent cross-origin.

**Fix**: Ensure `ALLOWED_ORIGINS` is strictly validated against a whitelist pattern and never includes `*`.

---

### 14. No HTTPS in Docker Compose

| File | Line | Issue |
|------|------|-------|
| `docker-compose.yml` | 8-9 | Database exposed on port 5432 without TLS |
| `docker-compose.yml` | 21-22 | Backend exposed on port 8000 without HTTPS |

**Impact**: All traffic (including credentials, JWT tokens, and secrets) is transmitted in plaintext within the container network and to the host.

**Fix**: Use a reverse proxy (e.g., nginx/Traefik) with TLS termination, or at minimum use Docker internal networks.

---

### 15. Broad Exception Handling Exposes Internal Details

| File | Line | Issue |
|------|------|-------|
| `backend/app/routers/api_tokens.py` | 116 | `detail=f"Failed to generate token: {str(e)}"` |
| `backend/app/routers/api_tokens.py` | 149 | `detail=f"Failed to recycle token: {str(e)}"` |

**Impact**: Internal error messages are returned to the client, potentially leaking stack traces, file paths, or database details.

**Fix**: Return a generic error message to the client; log the full exception server-side.

---

## 🔵 LOW

### 16. No HSTS Preload

| File | Line | Issue |
|------|------|-------|
| `backend/app/main.py` | 37 | `Strict-Transport-Security: max-age=31536000` is set but `; includeSubDomains; preload` is missing |

**Impact**: Browsers won't preload HSTS, making the first request vulnerable to downgrade attacks.

**Fix**: Add `; includeSubDomains; preload` to the HSTS header.

---

### 17. No Client-Side Token Expiration Handling

| File | Line | Issue |
|------|------|-------|
| `frontend/src/contexts/AuthContext.tsx` | 23-42 | Token is stored in localStorage but never checked for expiration |

**Impact**: The frontend keeps the token in localStorage even after it expires (480 minutes / 8 hours). The user won't be redirected to login until they make an API call that returns 401.

**Fix**: Parse the `exp` claim from the JWT and redirect to login when expired.

---

## Summary

| Severity | Count | Key Themes |
|----------|-------|------------|
| 🔴 Critical | 4 | Hardcoded credentials, JWT bypass, auth bypass, user enumeration |
| 🟠 High | 6 | Missing rate limits, encryption key management, DoS, sensitive data exposure |
| 🟡 Medium | 5 | Weak passwords, IP spoofing, CORS, no HTTPS, error leakage |
| 🔵 Low | 2 | HSTS preload, token expiration UX |

### Top 3 Immediate Actions
1. **Remove all hardcoded credentials** and enforce secrets via environment variables or Docker secrets
2. **Fix the JWT secret** — use a cryptographically random key and consider RS256
3. **Remove or protect the unprotected `/api/users` and `/api/groups` endpoints** in `groups.py` that bypass admin authorization
