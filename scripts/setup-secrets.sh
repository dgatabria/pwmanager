#!/usr/bin/env bash
# setup-secrets.sh - Generate and configure all secrets for a new deployment.
# Usage: ./scripts/setup-secrets.sh
#
# This script creates:
#   - backend/secrets/*.txt (Local development secrets)
#   - .env.db              (Database env file)
#   - .env.backend         (Backend env file)
#
# IMPORTANT: Run this script only once per deployment.
#            Do NOT run it again unless you want to rotate all secrets.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "🔐 Generating secrets for ia-tests-2..."

# Create directories
mkdir -p "$SCRIPT_DIR/backend/secrets"

# Generate secrets
echo "  - postgres_password"
openssl rand -hex 32 > "$SCRIPT_DIR/backend/secrets/postgres_password.txt"

echo "  - secret_key (JWT)"
openssl rand -hex 32 > "$SCRIPT_DIR/backend/secrets/secret_key.txt"

echo "  - encryption_key (Fernet)"
openssl rand -base64 32 > "$SCRIPT_DIR/backend/secrets/encryption_key.txt"

# Create .env.db
cat > "$SCRIPT_DIR/.env.db" <<EOF
# Local development database configuration
# DO NOT commit this file to version control
POSTGRES_DB=password_manager
POSTGRES_USER=postgres
POSTGRES_PASSWORD=$(cat "$SCRIPT_DIR/backend/secrets/postgres_password.txt")
EOF

# Create .env.backend
cat > "$SCRIPT_DIR/.env.backend" <<EOF
# Local development backend configuration
# DO NOT commit this file to version control
DATABASE_URL=postgresql+asyncpg://postgres:$(cat "$SCRIPT_DIR/backend/secrets/postgres_password.txt")@db:5432/password_manager
ENCRYPTION_KEY=$(cat "$SCRIPT_DIR/backend/secrets/encryption_key.txt")
EOF

echo ""
echo "✅ Secrets generated successfully!"
echo ""
echo "Next steps:"
echo "  1. Review the generated files in backend/secrets/"
echo "  2. Ensure .env.db and .env.backend are NOT committed to version control"
echo "  3. Run docker-compose up to start the application"
echo ""
echo "⚠️  WARNING: These secrets are critical. Back them up securely."
echo "            If lost, all encrypted data becomes unrecoverable."
