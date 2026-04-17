#!/bin/bash
# Run script for Credit Card Statement Analyzer

COMMAND="$1"
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

# Run the application
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
