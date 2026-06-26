#!/usr/bin/env bash
set -euo pipefail

echo "Running database migrations..."
python3 seed.py --migrate-only

echo "Starting Uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
