#!/bin/bash
# thinkstack: development server
# starts the fastapi backend (and tauri frontend when available)
# usage: ./scripts/dev.sh
set -e

echo "----------------------------------------"
echo "thinkstack: development mode"
echo "----------------------------------------"

source .venv/bin/activate

echo "starting fastapi backend on port 8000..."
uvicorn main:app --reload --port 8000 &
BACKEND_PID=$!

if [ -f "src-tauri/tauri.conf.json" ]; then
    echo "starting tauri frontend..."
    npm run tauri dev &
    FRONTEND_PID=$!
else
    echo "tauri not scaffolded. running backend only."
    echo "api docs available at http://localhost:8000/docs"
fi

cleanup() {
    echo ""
    echo "shutting down..."
    kill $BACKEND_PID 2>/dev/null
    [ -n "$FRONTEND_PID" ] && kill $FRONTEND_PID 2>/dev/null
    exit 0
}

trap cleanup SIGINT SIGTERM EXIT
wait
