#!/bin/bash
# Run script for Credit Card Statement Analyzer

set -euo pipefail

COMMAND="${1:-}"
shift || true

echo "Starting Credit Card Statement Analyzer..."
echo ""

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
    echo "✓ Virtual environment activated"
else
    echo "⚠ Virtual environment not found. Creating..."
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
fi

echo ""

# CLI user management commands
if [ "$COMMAND" = "create-user" ] || [ "$COMMAND" = "set-password" ]; then
    python manage_user.py "$COMMAND" "$@"
    exit $?
fi

echo "Starting FastAPI server..."
echo "Access the application at: http://localhost:8000"
echo ""

# Runtime configuration
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
APP_ENV="${APP_ENV:-development}"
UVICORN_RELOAD="${UVICORN_RELOAD:-}"

if [ -z "$UVICORN_RELOAD" ]; then
    if [ "$APP_ENV" = "development" ]; then
        UVICORN_RELOAD="true"
    else
        UVICORN_RELOAD="false"
    fi
fi

if [ "$UVICORN_RELOAD" = "true" ]; then
    uvicorn app.main:app --host "$HOST" --port "$PORT" --reload
else
    uvicorn app.main:app --host "$HOST" --port "$PORT"
fi
