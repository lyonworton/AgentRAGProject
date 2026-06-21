#!/usr/bin/env bash
# ============================================================
# AgentRAG — Full-stack launcher (Docker-only)
# All services run inside Docker containers.
# Prerequisites: Docker + Docker Compose, NVIDIA Container Toolkit
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "============================================================"
echo "  AgentRAG — Multi-Agent RAG System"
echo "  GPU Embedding via Xinference (bge-m3)"
echo "============================================================"
echo ""

# ---------- Pre-flight checks ----------

# Check Docker
if ! command -v docker &>/dev/null; then
    echo "[ERROR] Docker is not installed or not in PATH."
    echo "        Install Docker Engine first."
    exit 1
fi
echo "[OK] Docker $(docker --version)"

# Check Docker Compose
if ! docker compose version &>/dev/null; then
    echo "[ERROR] Docker Compose plugin not found."
    exit 1
fi
echo "[OK] Docker Compose available"

# Check .env
if [ ! -f .env ]; then
    echo "[WARN] .env not found. Copying .env.example → .env"
    echo "       Please edit .env with your API keys before starting."
    cp .env.example .env
fi

# Check NVIDIA Docker
if docker info 2>&1 | grep -q "nvidia"; then
    echo "[OK] NVIDIA runtime detected — GPU enabled"
    GPU_ENABLED=true
else
    echo "[WARN] NVIDIA Docker runtime not detected."
    echo "       GPU acceleration will NOT be available."
    GPU_ENABLED=false
fi

echo ""
echo "---------- Starting services ----------"
echo ""

# Build and start all services
docker compose up --build -d

if [ $? -ne 0 ]; then
    echo ""
    echo "[ERROR] Failed to start services. Check logs:"
    echo "        docker compose logs -f"
    exit 1
fi

echo ""
echo "---------- Waiting for services to be ready ----------"
echo ""

# Wait for core services
echo "Waiting for PostgreSQL, Milvus, Redis..."
TIMEOUT=90
ELAPSED=0
INTERVAL=5

while [ $ELAPSED -lt $TIMEOUT ]; do
    REMAINING=$((TIMEOUT - ELAPSED))
    echo -n "  [.!] ${REMAINING}s remaining... "

    # Check if core ports are listening
    if ss -tln | grep -qE ':(5432|19530|6379)\b'; then
        echo "[OK] Core services reachable."
        break
    fi

    sleep $INTERVAL
    ELAPSED=$((ELAPSED + INTERVAL))
done

if [ $ELAPSED -ge $TIMEOUT ]; then
    echo ""
    echo "[WARN] Some services may not be fully ready yet."
    echo "       This is normal on first start — models need to download."
fi

echo ""
echo "============================================================"
echo "  AgentRAG is starting up!"
echo "============================================================"
echo ""
echo "  Frontend:        http://localhost:3000"
echo "  Backend API:     http://localhost:8000/docs"
echo "  Neo4j Browser:   http://localhost:7474"
echo "  Elasticsearch:   http://localhost:9200"
echo ""
echo "  Default login:   admin / admin"
echo "  Reset password:  python scripts/reset_admin_pwd.py"
echo ""
echo "  View logs:       docker compose logs -f"
echo "  Stop services:   docker compose down"
echo "  Stop + remove:   docker compose down -v"
echo ""
echo "  Xinference bge-m3 model loads automatically on first access."
echo "  If GPU is available, embedding will be fast."
echo ""
