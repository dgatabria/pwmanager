# 🔐 Password Manager

Sistema de gestión de secretos corporativos con autenticación JWT (RS256), control de acceso por roles (RBAC), encriptación de secretos en reposo (Fernet) y registro de auditoría completo.

## Arquitectura

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Frontend   │────▶│   Backend    │────▶│    Postgres  │
│  React + Vite│  API│  FastAPI     │  ORM│  (asyncpg)   │
│  :3000       │     │  :8000       │     │  :5432       │
└──────────────┘     └──────────────┘     └──────────────┘
```

- **Frontend**: React 18 + TypeScript + TailwindCSS (Vite dev server con proxy `/api` → backend)
- **Backend**: FastAPI + SQLAlchemy async + asyncpg
- **Auth**: JWT RS256 (par de claves RSA autogenerado, persistido en disco)
- **Encriptación**: Fernet (AES-128-CBC) para secretos en reposo
- **RBAC**: Grupos de usuarios → Grupos de secretos (lectura/escritura)
- **Audit**: Registro de revelado y copiado de secretos con IP, user-agent y timestamp

## Requisitos

- Docker + Docker Compose
- OpenSSL (para generación de secretos)

## Instalación Rápida (Desarrollo)

```bash
# 1. Clonar el repositorio
git clone https://github.com/dgatabria/ia-tests-2.git
cd ia-tests-2

# 2. Generar secretos y levantar el entorno
./deploy.sh dev
```

Esto genera automáticamente:
- Contraseña aleatoria de PostgreSQL
- Clave de encriptación Fernet
- Clave JWT (ya generada por el código al arrancar)
- Archivos `.env.db` y `.env.backend` (git-ignored)
- Usuario admin inicial + grupos por defecto

### Acceder

| Servicio | URL |
|----------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| Docs Swagger | http://localhost:8000/docs |

El usuario admin se crea automáticamente con una contraseña generada al azar. Si necesitás resetearla, ejecutá:

```bash
./deploy.sh seed   # Re-seedea la base (no crea otro admin si ya existe)
```

## Despliegue en Producción

### Opción A: Variables de entorno

```bash
export POSTGRES_PASSWORD=$(openssl rand -hex 32)
export DATABASE_URL="postgresql+asyncpg://postgres:${POSTGRES_PASSWORD}@db:5432/password_manager"
export ENCRYPTION_KEY=$(openssl rand -base64 32)

./deploy.sh prod
```

### Opción B: Archivos `.env`

Generá los archivos manualmente (o con `./deploy.sh secrets`):

```bash
# .env.db
POSTGRES_DB=password_manager
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<generar con openssl rand -hex 32>

# .env.backend
DATABASE_URL=postgresql+asyncpg://postgres:<password>@db:5432/password_manager
ENCRYPTION_KEY=<generar con openssl rand -base64 32>
```

Luego:

```bash
./deploy.sh prod
```

### Opción C: Docker secrets

```bash
docker secret create postgres_password <(openssl rand -hex 32)
docker secret create encryption_key <(openssl rand -base64 32)
```

El backend lee automáticamente de `/run/secrets/<nombre>` como fallback si no hay variables de entorno.

### Variables de entorno obligatorias en producción

En producción, **nunca** uses valores por defecto ni hardcodeados. Todas estas variables deben provenir de un gestor de secretos (Vault, AWS Secrets Manager, etc.) o Docker secrets:

| Variable | Descripción | Cómo generar |
|----------|-------------|--------------|
| `DATABASE_URL` | Connection string de PostgreSQL | `postgresql+asyncpg://user:pass@host:5432/dbname` |
| `ENCRYPTION_KEY` | Clave Fernet (32 bytes base64) para encriptar secretos en reposo | `openssl rand -base64 32` |
| `POSTGRES_PASSWORD` | Contraseña del usuario PostgreSQL | `openssl rand -hex 32` |
| `RSA_KEY_PASSPHRASE` | **Opcional pero recomendado**: passphrase para cifrar la clave privada RSA en disco | Cualquier string aleatorio seguro |
| `DOCS_ENABLED` | **Debe ser `false` en producción**. Habilita Swagger UI y ReDoc | `true` (dev) o `false` (prod) |

> ⚠️ **Sin `ENCRYPTION_KEY`, todos los secretos encriptados se pierden para siempre.**
> ⚠️ **Sin `POSTGRES_PASSWORD`, la base de datos no arranca.**
> ⚠️ **Si no se configura `RSA_KEY_PASSPHRASE`, la clave privada JWT se almacena sin cifrar en disco — cualquiera con acceso al filesystem puede forjar tokens de admin.**
> ⚠️ **Si `DOCS_ENABLED=true` en producción, se expone la documentación interactiva de la API — revela endpoints, schemas y comportamientos internos.**

> ⚠️ **Importante para producción**:
> - Configurar un reverse proxy (nginx/Traefik) con TLS terminando HTTPS
> - El `docker-compose.yml` expone puertos sin HTTPS
> - PostgreSQL **no expone puertos** — solo es accesible dentro de la red Docker
> - Hacer backup de `backend/secrets/*.txt` y `.env.*` — sin ellos, los datos encriptados se pierden para siempre

## Comandos Disponibles

```bash
./deploy.sh dev       # Dev: genera secretos + levanta Docker + seedea la DB
./deploy.sh prod      # Prod: levanta Docker (requiere secretos pre-configurados)
./deploy.sh secrets   # Genera secretos aleatorios (sobreescribe existentes)
./deploy.sh seed      # Seedea la base de datos (admin + grupos)
./deploy.sh clean     # Elimina todos los secretos y archivos generados
```

## Password Manager CLI

Herramienta de línea de comandos **standalone** para interactuar con el Password Manager desde la terminal. Funciona en **Linux** y **Windows** (con Python 3.8+).

**Cero dependencias del servidor** — un cliente puede clonar el repo, borrar todo lo que no usa (backend, frontend, docker-compose.yml, etc.), quedarse solo con `cli/` y `scripts/`, y apuntar la herramienta a cualquier servidor remoto.

### Instalación

```bash
# Opción A: Clonar todo y usar solo la CLI
git clone https://github.com/dgatabria/ia-tests-2.git
cd ia-tests-2
rm -rf backend frontend docker-compose.yml deploy.sh .env*  # lo que no necesitás
pip install -r cli/requirements.txt

# Opción B: Instalar desde cualquier lugar (ya clonado)
pip install -r cli/requirements.txt
```

### Configuración de API Key

La CLI lee la API key en este orden de prioridad:

1. **Flag** `--api-key <key>`
2. **Variable de entorno** ``
3. **Archivo** `~/.secretsmanager/apikey` (con permisos `0600`)

```bash
# Opción 1: Variable de entorno
export SECRETSMANAGER_API_KEY=tu-api-key-aqui

# Opción 2: Guardar en archivo (recomendado)
./scripts/passwordmanager setup
# O manualmente:
mkdir -p ~/.secretsmanager
echo "tu-api-key-aqui" > ~/.secretsmanager/apikey
chmod 600 ~/.secretsmanager/apikey

# Opción 3: Flag directo
./scripts/passwordmanager --api-key tu-api-key-aqui list secret
```

### Configuración de Base URL

```bash
# Variable de entorno
export SECRETSMANAGER_BASE_URL=https://pm.example.com

# Flag directo
./scripts/passwordmanager --base-url https://pm.example.com list secret
```

### Uso

```bash
# Lista todos los secretos
./scripts/passwordmanager list secret

# Lista secretos filtrados por grupo
./scripts/passwordmanager list secret --group 1

# Lista todos los grupos de secretos
./scripts/passwordmanager list group

# Crear un nuevo secreto (interactivo)
./scripts/passwordmanager create secret

# Crear un secreto con datos en línea de comandos (no interactivo)
./scripts/passwordmanager create secret "Mi Contraseña" -t password -D "secreto123" -g 1

# Generar y guardar una nueva SSH key
./scripts/passwordmanager create secret-ssh

# Recuperar un secreto por ID
./scripts/passwordmanager retrieve secret 1

# Recuperar un secreto por nombre
./scripts/passwordmanager retrieve secret "Mi Contraseña"

# Revelar un secreto con datos descifrados
./scripts/passwordmanager reveal secret 1

# Revelar un secreto por nombre
./scripts/passwordmanager reveal secret "Mi ContraseÃ±a"

# Eliminar un secreto
./scripts/passwordmanager delete secret 1

# Crear un nuevo grupo de secretos
./scripts/passwordmanager create group "Infraestructura" -d "Secretos de infra"

# Listar API tokens
./scripts/passwordmanager token list

# Crear un nuevo API token
./scripts/passwordmanager token create "Mi Token"
```

### Sintaxis General

```
passwordmanager <comando> [subcomando] [argumento]
```

| Comando | Subcomando | Descripción |
|---------|------------|-------------|
| `list` | `secret` | Listar todos los secretos |
| `list` | `group` | Listar todos los grupos de secretos |
| `create` | `secret` | Crear un nuevo secreto (interactivo) |
| `create` | `secret-ssh` | Generar y guardar una SSH key |
| `create` | `group` | Crear un nuevo grupo de secretos |
| `retrieve` | `secret` | Recuperar un secreto por ID o nombre |
| `retrieve` | `secret-ssh` | Recuperar una SSH key |
| `delete` | `secret` | Eliminar un secreto |
| `delete` | `group` | Eliminar un grupo de secretos |
| `token` | `list` | Listar API tokens |
| `token` | `create` | Crear un nuevo API token |
| `token` | `revoke` | Revocar un API token |
| `setup` | — | Guardar API key en archivo |

### Ejemplos Avanzados

```bash
# Usar con URL remota y token en variable de entorno
SECRETSMANAGER_BASE_URL=https://pm.prod.com SECRETSMANAGER_API_KEY=abc123 ./scripts/passwordmanager list secret

# Crear SSH key de 2048 bits con comentario personalizado
./scripts/passwordmanager create secret-ssh -k 2048 -c "dev@laptop"

# Crear secreto con username y URL
./scripts/passwordmanager create secret "GitHub" -t password -u "miusuario" -U "https://github.com" -D "secreto123"

# Output JSON (para scripts)
./scripts/passwordmanager list secret --json
```

### Estructura del CLI

```
cli/                          # CLI standalone (sin dependencias del servidor)
├── __init__.py               # Paquete Python
├── config.py                 # Cargador de configuración (API key, base URL)
├── api.py                    # Cliente HTTP (PMClient)
├── utils.py                  # Colores, tablas, helpers
├── passwordmanager.py        # Entry point con argparse
└── requirements.txt          # Dependencia: requests>=2.28.0
scripts/
└── passwordmanager           # Wrapper bash (Linux/macOS)
```

## Desarrollo Local (sin Docker)

### Backend

```bash
cd backend

# Crear env y levantar
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Generar secretos manualmente
mkdir -p secrets
openssl rand -hex 32 > secrets/postgres_password.txt
openssl rand -base64 32 > secrets/encryption_key.txt

# Configurar .env
cat > .env <<EOF
DATABASE_URL=postgresql+asyncpg://postgres:$(cat secrets/postgres_password.txt)@localhost:5432/password_manager
ENCRYPTION_KEY=$(cat secrets/encryption_key.txt)
EOF

# Levantar
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend

npm install
npm run dev
```

El frontend dev server proxyea las peticiones `/api/*` al backend en `localhost:8000`.

### Seedear la base

```bash
cd backend

# Exportar las variables obligatorias (las mismas que para el backend)
export DATABASE_URL=postgresql+asyncpg://postgres:$(cat secrets/postgres_password.txt)@localhost:5432/password_manager
export ENCRYPTION_KEY=$(cat secrets/encryption_key.txt)

python seed.py
```

## Estructura del Proyecto

```
ia-tests-2/
├── cli/                          # CLI standalone (sin dependencias del servidor)
│   ├── __init__.py               # Package init
│   ├── config.py                 # Config loader (API key, base URL)
│   ├── api.py                    # PMClient HTTP client
│   ├── utils.py                  # Terminal colors, table formatter
│   ├── passwordmanager.py        # Main CLI entry point
│   └── requirements.txt          # Dependency: requests>=2.28.0
├── backend/                      # Backend FastAPI (server-side only)
│   ├── app/
│   │   ├── main.py               # Aplicación FastAPI + middleware
│   │   ├── config.py             # Configuración de secretos
│   │   ├── database.py           # Motor SQLAlchemy async
│   │   ├── migrations/
│   │   │   ├── __init__.py       # Migration runner
│   │   │   └── 001_add_owner_id.py  # Add owner_id to secret_groups
│   │   ├── routers/              # Endpoints API
│   │   │   ├── auth.py           # Login, registro, perfil
│   │   │   ├── admin.py          # Admin: usuarios, SAML, key rotation
│   │   │   ├── secrets.py        # CRUD de secretos
│   │   │   ├── api_tokens.py     # Tokens de API programáticos
│   │   │   ├── groups.py         # Membresía de grupos
│   │   │   └── secret_groups.py  # Grupos de secretos (owner-based RBAC)
│   │   ├── services/
│   │   │   ├── auth.py           # JWT RS256
│   │   │   ├── encryption.py     # Fernet encryption
│   │   │   ├── api_token.py      # API token management
│   │   │   └── audit.py          # Audit logging
│   │   ├── models/               # Modelos SQLAlchemy
│   │   ├── schemas/              # Pydantic schemas
│   │   └── utils/
│   │       ├── security.py       # Password hashing (bcrypt)
│   │       └── rsa_keys.py       # RSA key pair management
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── seed.py                   # Seed script (admin + grupos)
│   └── secrets/                  # Secrets locales (git-ignored)
├── frontend/                     # Frontend React + Vite
│   ├── src/
│   │   ├── App.tsx               # Router + auth guard
│   │   ├── main.tsx              # Entry point
│   │   ├── components/
│   │   │   ├── AddSecretButton.tsx
│   │   │   ├── AdminAuthMethod.tsx
│   │   │   ├── AdminBackupRecovery.tsx
│   │   │   ├── AdminUserManagement.tsx
│   │   │   ├── CreateSecretGroupModal.tsx  # New: group creation with visibility
│   │   │   ├── GroupSidebar.tsx            # Updated: owner badges + access indicators
│   │   │   ├── SearchBar.tsx
│   │   │   ├── SecretDetail.tsx
│   │   │   ├── SecretForm.tsx
│   │   │   ├── SecretList.tsx
│   │   │   └── UserManagement.tsx
│   │   ├── contexts/
│   │   │   └── AuthContext.tsx
│   │   ├── pages/
│   │   │   ├── AdminDashboard.tsx
│   │   │   ├── Dashboard.tsx               # Updated: group creation modal
│   │   │   ├── Login.tsx
│   │   │   └── Preferences.tsx
│   │   ├── services/
│   │   │   └── api.ts
│   │   ├── types/
│   │   │   └── index.ts
│   │   └── utils/
│   │       └── url.ts
│   ├── package.json
│   └── vite.config.ts            # Proxy /api → localhost:8000
├── scripts/
│   ├── setup-secrets.sh          # Legacy secret generation script
│   └── passwordmanager           # CLI launcher (Linux/macOS)
├── docker-compose.yml            # Docker orchestration
├── deploy.sh                     # Deployment script
├── .env.example                  # Template de variables
├── .env.db                       # DB config (git-ignored)
├── .env.backend                  # Backend config (git-ignored)
├── .gitignore
└── README.md
```

## API Endpoints

### Autenticación

| Método | Endpoint | Auth | Descripción |
|--------|----------|------|-------------|
| POST | `/login` | No | Login (rate limited: 5/min) |
| POST | `/register` | No | Registro de usuario (rate limited: 10/h) |
| GET | `/me` | JWT | Perfil del usuario actual |

### Secretos

| Método | Endpoint | Auth | Descripción |
|--------|----------|------|-------------|
| GET | `/api/secrets` | JWT | Listar secretos |
| GET | `/api/secrets/{id}` | JWT | Ver secreto (desencriptado) |
| POST | `/api/secrets` | JWT | Crear secreto |
| PUT | `/api/secrets/{id}` | JWT | Actualizar secreto |
| DELETE | `/api/secrets/{id}` | JWT | Desactivar secreto (soft delete) |
| GET | `/api/secrets/{id}/masked` | JWT | Ver con datos enmascarados |
| GET | `/api/secrets/{id}/reveal` | JWT | Revelar datos (con audit log) |
| POST | `/api/secrets/{id}/copy` | JWT | Copiar al clipboard (con audit log) |
| POST | `/api/secrets/ssh-key/generate` | JWT | Generar par de claves SSH |

### API Tokens

| Método | Endpoint | Auth | Descripción |
|--------|----------|------|-------------|
| GET | `/api/api-tokens` | JWT/API Key | Listar tokens |
| POST | `/api/api-tokens/generate` | JWT | Generar token |
| POST | `/api/api-tokens/recycle` | JWT | Rotar token |
| DELETE | `/api/api-tokens/{id}` | JWT | Revocar token |

### Admin (Superuser)

| Método | Endpoint | Auth | Descripción |
|--------|----------|------|-------------|
| GET | `/api/admin/users` | JWT + Superuser | Listar usuarios |
| POST | `/api/admin/users` | JWT + Superuser | Crear usuario |
| PUT | `/api/admin/users/{id}` | JWT + Superuser | Actualizar usuario |
| POST | `/api/admin/users/{id}/reset-password` | JWT + Superuser | Resetear password |
| POST | `/api/admin/users/{id}/toggle-active` | JWT + Superuser | Activar/desactivar |
| PUT | `/api/admin/auth/method` | JWT + Superuser | Cambiar auth method |
| PUT | `/api/admin/auth/saml` | JWT + Superuser | Configurar SAML |
| POST | `/api/admin/secrets/rotate-key` | JWT + Superuser | Rotar clave de encriptación |

## Seguridad

| Característica | Implementación |
|----------------|----------------|
| Autenticación | JWT RS256 (asimétrico, par RSA autogenerado) |
| Passwords | bcrypt con salt + política de complejidad (mín. 12 chars, mayúscula, minúscula, dígito, carácter especial) |
| Secrets en reposo | Fernet (AES-128-CBC) |
| Rate limiting | slowapi (5 req/min en login, 10/h en registro, 60/min en endpoints admin y secret access) |
| Audit logging | IP, user-agent, timestamp en reveal/copy |
| Headers seguridad | HSTS, X-Frame-Options: DENY, CSP, nosniff |
| RBAC | Grupos → Secret groups (read/write) |

## Licencia

MIT — Véase el archivo [LICENSE](LICENSE).
