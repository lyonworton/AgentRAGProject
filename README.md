# AgentRAG

Intelligent RAG (Retrieval-Augmented Generation) system with multi-agent architecture.

## Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌──────────────┐
│  Frontend    │────▶│  FastAPI Backend  │────▶│  Ingestion    │
│  (Docker)   │     │  (Local GPU)      │     │  Worker       │
│  :3000       │     │  :8081            │     │  (Local GPU)  │
└─────────────┘     └──────────────────┘     └──────────────┘
                            │
                    ┌───────┴──────────┐
                    │  Docker Infra    │
                    │  :5432 PostgreSQL│
                    │  :19530 Milvus   │
                    │  :6379 Redis     │
                    │  :7687 Neo4j     │
                    │  :9200 Elasticsearch│
                    └──────────────────┘
```

| Component | Deployment | GPU |
|-----------|-----------|-----|
| Frontend (React) | Docker | N/A |
| Backend (FastAPI) | **Local** | Yes |
| Worker (ARQ) | **Local** | Yes |
| Postgres/Milvus/Redis/Neo4j/ES | Docker | N/A |

## Quick Start

### Prerequisites

- Python 3.12+ with Conda (for GPU PyTorch + SentenceTransformers + FlagEmbedding)
- Docker + Docker Compose
- NVIDIA GPU (GTX 1660 SUPER or better) with driver 451.48+
- GPU models at `D:/models/BAAI/`:
  - `bge-m3` (embedding)
  - `bge-reranker-v2-m3` (reranker)

### Option 1: Local Dev (GPU) — Recommended

```bash
# 1. Start infrastructure (Docker)
docker compose up -d

# 2. Start backend + worker (Local GPU)
# Windows:
run-local.bat
# Linux/macOS:
chmod +x run-local.sh && ./run-local.sh
```

Access:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8081/docs
- Neo4j Browser: http://localhost:7474

### Option 2: Full Docker (no GPU acceleration)

```bash
# Build and run everything in Docker
# Note: GPU passthrough requires TCC mode + compatible driver
docker compose build && docker compose up
```

## GPU Acceleration

GPU is enabled for:
- **BGE-M3 Embedding**: `SentenceTransformer(device="cuda")`
- **BGE Reranker**: `FlagReranker(..., devices="cuda:0")`

Verify GPU:
```bash
python tests/gpu_verify.py
```

Expected output:
```
CUDA available:        OK
GPU detected:          OK (GeForce GTX 1660 SUPER)
Model loaded:          OK
GPU VRAM used:         ~1900 MB
Overall:               PASS
```

## Configuration

Copy `.env` and adjust as needed:

| Variable | Default | Notes |
|----------|---------|-------|
| `BGE_EMBEDDING_MODEL` | `D:/models/BAAI/bge-m3` | Path to embedding model |
| `RERANKER_MODEL` | `D:/models/BAAI/bge-reranker-v2-m3` | Path to reranker model |
| `use_gpu` | `True` | Enable GPU for embedding+reranker |
| `LLM_PROVIDER` | `openai` | `openai` or `ollama` |
| `OPENAI_BASE_URL` | `https://api.deepseek.com/v1` | LLM API endpoint |

## Project Structure

```
app/
├── adapters/       # LLM, embedding, reranker, vector store, search
├── agents/         # Multi-agent graph (router, understander, executor...)
├── api/v1/         # REST API endpoints
├── core/           # Config, LLM factory, embedding factory, DI
├── domain/         # DB models
├── ingestion/      # Pipeline, parsers, sources, writers
├── tools/          # Search tools (semantic, keyword, KG, web)
├── workers/        # ARQ workers (ingest, repair)
frontend/
└── src/            # React + TypeScript
```

## Development

```bash
# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/

# Run specific test
pytest tests/unit/agents/test_router.py -v
```

## License

Private.
