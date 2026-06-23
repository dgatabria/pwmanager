#!/usr/bin/env bash
# init-db-user.sh — Create a dedicated application user with least-privilege access.
#
# This script runs once after the PostgreSQL container is healthy.
# It creates a dedicated app role and grants it minimal privileges.
#
# Required environment variables:
#   POSTGRES_USER     — superuser name (default: postgres)
#   POSTGRES_PASSWORD — superuser password
#   POSTGRES_DB       — database name
#   APP_USER          — dedicated app username
#   APP_PASSWORD      — dedicated app password
#
# This script is idempotent — safe to run multiple times.

set -euo pipefail

PG_USER="${POSTGRES_USER:-postgres}"
PG_PASSWORD="${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}"
PG_DB="${POSTGRES_DB:-password_manager}"
APP_USER="${APP_USER:?APP_USER is required}"
APP_PASSWORD="${APP_PASSWORD:?APP_PASSWORD is required}"

export PGPASSWORD="$PG_PASSWORD"

echo "Creating dedicated database user '${APP_USER}'..."

psql -U "$PG_USER" -d "$PG_DB" <<EOSQL
-- Create the app role if it does not already exist
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '${APP_USER}') THEN
        CREATE ROLE ${APP_USER} NOLOGIN PASSWORD '${APP_PASSWORD}';
        RAISE NOTICE 'Created role ${APP_USER}';
    ELSE
        -- Update password in case it changed
        ALTER ROLE ${APP_USER} PASSWORD '${APP_PASSWORD}';
        RAISE NOTICE 'Updated password for role ${APP_USER}';
    END IF;
END
\$\$;

-- Grant privileges on the database
GRANT CONNECT ON DATABASE "${PG_DB}" TO "${APP_USER}";

-- Grant schema usage and creation (needed for migrations/seed)
GRANT USAGE ON SCHEMA public TO "${APP_USER}";
GRANT CREATE ON SCHEMA public TO "${APP_USER}";

-- Grant privileges on all existing tables
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "${APP_USER}";
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO "${APP_USER}";
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO "${APP_USER}";

-- Set default privileges for future tables created by postgres superuser
ALTER DEFAULT PRIVILEGES FOR ROLE "${PG_USER}" IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "${APP_USER}";
ALTER DEFAULT PRIVILEGES FOR ROLE "${PG_USER}" IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO "${APP_USER}";
ALTER DEFAULT PRIVILEGES FOR ROLE "${PG_USER}" IN SCHEMA public
    GRANT EXECUTE ON FUNCTIONS TO "${APP_USER}";

-- Also set default privileges for future tables created by the app user itself
ALTER DEFAULT PRIVILEGES FOR ROLE "${APP_USER}" IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "${APP_USER}";
ALTER DEFAULT PRIVILEGES FOR ROLE "${APP_USER}" IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO "${APP_USER}";
ALTER DEFAULT PRIVILEGES FOR ROLE "${APP_USER}" IN SCHEMA public
    GRANT EXECUTE ON FUNCTIONS TO "${APP_USER}";

EOSQL

echo "✓ Dedicated user '${APP_USER}' created with minimal privileges."
