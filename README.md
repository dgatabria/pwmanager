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

> ⚠️ **Importante para producción**:
> - Configurar un reverse proxy (nginx/Traefik) con TLS terminando HTTPS
> - El `docker-compose.yml` expone puertos sin HTTPS
> - No exponer el puerto 5432 de PostgreSQL fuera del host
> - Hacer backup de `backend/secrets/*.txt` y `.env.*` — sin ellos, los datos encriptados se pierden para siempre

## Comandos Disponibles

```bash
./deploy.sh dev       # Dev: genera secretos + levanta Docker + seedea la DB
./deploy.sh prod      # Prod: levanta Docker (requiere secretos pre-configurados)
./deploy.sh secrets   # Genera secretos aleatorios (sobreescribe existentes)
./deploy.sh seed      # Seedea la base de datos (admin + grupos)
./deploy.sh clean     # Elimina todos los secretos y archivos generados
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
python seed.py
```

## Estructura del Proyecto

```
ia-tests-2/
├── backend/                      # Backend FastAPI
│   ├── app/
│   │   ├── main.py               # Aplicación FastAPI + middleware
│   │   ├── config.py             # Configuración de secretos
│   │   ├── database.py           # Motor SQLAlchemy async
│   │   ├── routers/              # Endpoints API
│   │   │   ├── auth.py           # Login, registro, perfil
│   │   │   ├── admin.py          # Admin: usuarios, SAML, key rotation
│   │   │   ├── secrets.py        # CRUD de secretos
│   │   │   ├── api_tokens.py     # Tokens de API programáticos
│   │   │   ├── groups.py         # Membresía de grupos
│   │   │   └── secret_groups.py  # Grupos de secretos
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
│   │   ├── components/           # UI components
│   │   ├── contexts/             # Auth context
│   │   ├── pages/                # Page components
│   │   └── services/             # API client
│   ├── package.json
│   └── vite.config.ts            # Proxy /api → localhost:8000
├── scripts/
│   └── setup-secrets.sh          # Script legacy de generación de secrets
├── docker-compose.yml            # Docker orchestration
├── deploy.sh                     # Script principal de despliegue
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
| Passwords | bcrypt con salt |
| Secrets en reposo | Fernet (AES-128-CBC) |
| Rate limiting | slowapi (5 req/min en login, 10/h en registro) |
| Audit logging | IP, user-agent, timestamp en reveal/copy |
| Headers seguridad | HSTS, X-Frame-Options: DENY, CSP, nosniff |
| RBAC | Grupos → Secret groups (read/write) |

## Licencia

MIT — Véase el archivo [LICENSE](LICENSE).
