#!/bin/bash
# Start local GPU services for AgentRAG (Linux/macOS/Git Bash)
# Prerequisites: Docker infra running via `docker compose up -d`
# Usage: ./run-local.sh

set -e

echo "============================================"
echo "AgentRAG Local GPU Services"
echo "============================================"

# Check if Docker infra is running
echo "[1/3] Checking Docker infrastructure..."
if ! docker ps --format '{{.Names}}' | grep -q postgres; then
    echo "ERROR: Docker infrastructure not running!"
    echo "Run: docker compose up -d"
    exit 1
fi
echo "OK: Docker services detected"

# Check if backend port is available
echo "[2/3] Checking port 8081..."
if command -v lsof &> /dev/null; then
    if lsof -i :8081 &> /dev/null; then
        echo "WARNING: Port 8081 is already in use."
    fi
elif command -v netstat &> /dev/null; then
    if netstat -an 2>/dev/null | grep ':8081.*LISTEN' &> /dev/null; then
        echo "WARNING: Port 8081 is already in use."
    fi
fi

echo "[3/3] Starting FastAPI (GPU enabled)..."
uvicorn app.main:app --host 0.0.0.0 --port 8081 &
BACKEND_PID=$!

echo "Starting ARQ Worker (GPU enabled)..."
python -m arq app.workers.main.WorkerSettings &
WORKER_PID=$!

echo ""
echo "============================================"
echo "Backend:  http://localhost:8081 (PID $BACKEND_PID)"
echo "Worker:   PID $WORKER_PID"
echo "Frontend: http://localhost:3000 (Docker)"
echo "============================================"
echo ""
echo "Press Ctrl+C to stop all services"

trap "echo 'Stopping...'; kill $BACKEND_PID $WORKER_PID 2>/dev/null; exit" INT TERM
wait
