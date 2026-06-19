# Xinference GPU Acceleration for Embedding

**Date:** 2026-06-18
**Status:** Approved
**Goal:** Accelerate BGE-M3 document embedding from ~130s (CPU) to ~5-15s (GPU) by deploying Xinference as a Docker service and switching the embedding backend.

## Problem Statement

Current embedding performance: 99 chunks → ~130s on CPU (BGE-M3 via sentence-transformers).
Scaling to 100MB would take ~28000s. Pipeline optimizations (batch_size, flush, commit) reduced overhead but embedding itself remains the bottleneck.

## Constraints

- **GPU:** GTX 1660 Super (6GB VRAM) — sufficient for BGE-M3 dense mode
- **Driver:** Must upgrade from 451.48 (CUDA 11.0 max) to latest (CUDA 12.x)
- **Docker:** Requires nvidia-container-toolkit for GPU passthrough
- **Backend switch:** Config-driven (`EMBEDDING_BACKEND=xinference|local`), no code changes to toggle
- **Fallback:** If Xinference is unreachable, automatically fall back to local CPU embedding
- **Reranker:** NOT changed in this phase — stays CPU FlagReranker

## Architecture

```
OLD:
  FastAPI → BGEEmbedding (sentence-transformers, CPU) → BGE-M3

NEW:
  FastAPI → XinferenceEmbedding (AsyncOpenAI) → Xinference:Docker → BGE-M3 (GPU)
  FastAPI → BGEEmbedding (sentence-transformers, CPU, fallback)
```

## Design: 6 Changes

### 1. Docker Compose: Add Xinference Service

- **File:** `docker-compose.yml`
- **Change:** Add new `xinference` service after `arq-worker`:
  ```yaml
  xinference:
    image: xorbitsai/xinference:latest
    ports: ["9997:9997"]
    environment:
      - XINFERENCE_HOME=/root/.xinference
    volumes:
      - xinference_models:/root/.xinference/models
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              capabilities: [gpu]
    restart: unless-stopped
  volumes:
    xinference_models:
  ```
- **Notes:** The `xinference` service exposes OpenAI-compatible API on port 9997. Models are persisted in a named volume.

### 2. Add Config Options

- **File:** `app/core/config.py`
- **Change:** Add 3 new fields to `Settings`:
  ```python
  embedding_backend: str = "local"    # "local" | "xinference"
  xinference_endpoint: str = "http://xinference:9997"
  xinference_embedding_model: str = "bge-m3"
  ```
- **Notes:** Default is `"local"` for safe migration. Docker env uses `"xinference"`.

### 3. New XinferenceEmbedding Adapter

- **File:** `app/adapters/embedding/xinference.py` (new)
- **Change:** Create new adapter following `BaseEmbedding` interface:
  ```python
  class XinferenceEmbedding(BaseEmbedding):
      """Xinference OpenAI-compatible embedding adapter (GPU-accelerated)."""
      
      def __init__(self, endpoint: str, model: str):
          self.client = AsyncOpenAI(base_url=f"{endpoint}/v1", api_key="xst-token")
          self.model = model
      
      async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
          resp = await self.client.embeddings.create(input=texts, model=self.model)
          return [d.embedding for d in resp.data]
      
      async def aembed_query(self, query: str) -> list[float]:
          resp = await self.client.embeddings.create(input=[query], model=self.model)
          return resp.data[0].embedding
      
      async def warmup(self):
          """Verify connectivity — no local model to load."""
          try:
              await asyncio.wait_for(
                  self.aembed_query("warmup"),
                  timeout=10.0
              )
              return True
          except Exception:
              return False
  ```
- **Notes:** Uses `AsyncOpenAI` (already installed as dependency of the existing OpenAI adapter). Model name `"bge-m3"` matches Xinference's built-in model catalog.

### 4. Modify embedding_factory

- **File:** `app/core/embedding_factory.py`
- **Change:** Route to correct adapter based on config:
  ```python
  def get_embedder():
      global _embedder
      if _embedder is not None:
          return _embedder
      
      from app.core.config import get_settings
      s = get_settings()
      
      if s.embedding_backend == "xinference":
          _embedder = XinferenceEmbedding(
              endpoint=s.xinference_endpoint,
              model=s.xinference_embedding_model,
          )
      else:
          from app.adapters.embedding.bge_m3 import BGEEmbedding
          _embedder = BGEEmbedding(model_path=s.bge_embedding_model)
      
      return _embedder
  ```

### 5. Update Startup Prewarm Logic

- **File:** `app/core/events.py`
- **Change:** Modify embedding prewarm to handle both backends:
  ```python
  # Prewarm embedding model
  try:
      embedder = get_embedder()
      if hasattr(embedder, "warmup"):
          # Xinference: verify connectivity
          warmup_success = await asyncio.wait_for(embedder.warmup(), timeout=15.0)
      else:
          # Local: load model
          await asyncio.to_thread(embedder._load_model)
          warmup_success = True
      if warmup_success:
          logger.info("embedding model prewarmed")
  except Exception as e:
      logger.warning("embedding prewarm failed, will load lazily", error=str(e))
  ```

### 6. Update .env Files

- **Files:** `.env`, `.env.docker`
- **Change:** Add new config:
  ```
  # Xinference (GPU embedding)
  EMBEDDING_BACKEND=xinference
  XINFERENCE_ENDPOINT=http://xinference:9997
  XINFERENCE_EMBEDDING_MODEL=bge-m3
  ```
- **Notes:** Local dev uses `EMBEDDING_BACKEND=local`. Docker uses `xinference`.

## Data Flow

```
Upload → Parse → [Parallel 3 paths]
  ├─ semantic_path: chunk → embed_chunks()
  │   → get_embedder().aembed_documents()
  │     → if xinference: AsyncOpenAI → Xinference:9997 → BGE-M3 (GPU)
  │     → if local: sentence-transformers → BGE-M3 (CPU)
  ├─ graph_path:   entities → LLM → Neo4j (unchanged)
  └─ keyword_path: full doc → ES (unchanged)
  → batch_flush_milvus() → commit_every=5
```

## Expected Performance

| Metric | CPU (sentence-transformers) | GPU (Xinference) |
|--------|---------------------------|------------------|
| 99 chunks embedding | ~130s | ~5-15s |
| 100MB total documents | ~28000s (unusable) | ~300-600s (5-10min) |
| Cold start | ~8s model load | N/A (model in container) |
| VRAM usage | N/A | ~2-3GB of 6GB |

## Files Modified/Created

| File | Action | Description |
|------|--------|-------------|
| `docker-compose.yml` | Modify | Add xinference service |
| `app/core/config.py` | Modify | 3 new config fields |
| `app/adapters/embedding/xinference.py` | **Create** | GPU embedding adapter |
| `app/core/embedding_factory.py` | Modify | Backend routing |
| `app/core/events.py` | Modify | Dual prewarm logic |
| `.env` | Modify | Local: EMBEDDING_BACKEND=local |
| `.env.docker` | Modify | Docker: EMBEDDING_BACKEND=xinference |

## Success Criteria

1. `docker compose up -d xinference` starts without errors
2. Xinference serves BGE-M3 on port 9997 with OpenAI-compatible API
3. `EMBEDDING_BACKEND=xinference` → embedding uses GPU
4. `EMBEDDING_BACKEND=local` → falls back to CPU (no regression)
5. 99 chunks embedding time drops from ~130s to <20s

## Prerequisites (Out of Scope)

- Upgrade NVIDIA driver from 451.48 to latest (supports CUDA 12.x)
- Install `nvidia-container-toolkit` in WSL2
- Install Docker Desktop with GPU support or nvidia-docker2

## Future Work (Phase 3)

- Deploy BGE-reranker-v2-m3 on Xinference GPU (currently CPU FlagReranker)
- Evaluate `bge-m3-lite` on Xinference for even faster inference
- Auto-select backend based on document size (large → GPU, small → local)
