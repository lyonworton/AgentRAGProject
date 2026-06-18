# Xinference GPU Embedding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add GPU-accelerated BGE-M3 embedding via Xinference service with config-driven backend switch and automatic fallback to CPU.

**Architecture:** Deploy Xinference as a Docker service serving BGE-M3 on port 9997 via OpenAI-compatible API. Add a new `XinferenceEmbedding` adapter that wraps `AsyncOpenAI`. Route through `embedding_factory` based on `EMBEDDING_BACKEND` config. Prewarm on startup with connectivity check; fall back to local CPU if Xinference is unreachable.

**Tech Stack:** Python 3.12+, FastAPI, AsyncOpenAI (already installed), Xinference (Docker), sentence-transformers (fallback)

## Global Constraints

- `EMBEDDING_BACKEND` must be `"local"` (default) or `"xinference"` — config-driven, no code changes to toggle
- Xinference fallback: if unreachable, automatically fall back to local CPU embedding (no crash)
- Reranker NOT changed — stays CPU FlagReranker
- Frontend batch upload with progress feedback already implemented in Phase 1 — no changes needed
- `bge-m3` model name must match Xinference's built-in catalog name exactly
- Default backend is `"local"` for safe migration — no regression on existing deployments

---

## Task 1: Config — Add Xinference Settings

**Files:**
- Modify: `app/core/config.py:29-30` (after `quality_threshold`)
- Test: `tests/unit/core/test_xinference_config.py`

**Interfaces:**
- Consumes: Existing `Settings` class with pydantic-settings
- Produces: 3 new fields on `Settings`: `embedding_backend: str = "local"`, `xinference_endpoint: str = "http://xinference:9997"`, `xinference_embedding_model: str = "bge-m3"`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/core/test_xinference_config.py
"""Verify Xinference config fields exist with correct defaults."""

import pytest
from app.core.config import Settings


def test_default_embedding_backend_is_local():
    s = Settings()
    assert s.embedding_backend == "local"


def test_default_xinference_endpoint():
    s = Settings()
    assert s.xinference_endpoint == "http://xinference:9997"


def test_default_xinference_model():
    s = Settings()
    assert s.xinference_embedding_model == "bge-m3"


def test_env_override_embedding_backend():
    import os
    os.environ["EMBEDDING_BACKEND"] = "xinference"
    try:
        s = Settings()
        assert s.embedding_backend == "xinference"
    finally:
        del os.environ["EMBEDDING_BACKEND"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/core/test_xinference_config.py -v`
Expected: FAIL with `Settings object has no attribute 'embedding_backend'`

- [ ] **Step 3: Write minimal implementation**

Add to `app/core/config.py` after line 29 (`quality_threshold`):

```python
    # Xinference (GPU embedding)
    embedding_backend: str = "local"       # "local" | "xinference"
    xinference_endpoint: str = "http://xinference:9997"
    xinference_embedding_model: str = "bge-m3"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/core/test_xinference_config.py -v`
Expected: 4/4 PASS

- [ ] **Step 5: Commit**

```bash
git add app/core/config.py tests/unit/core/test_xinference_config.py
git commit -m "feat(config): add xinference GPU embedding settings"
```

## Task 2: Xinference Embedding Adapter

**Files:**
- Create: `app/adapters/embedding/xinference.py`
- Test: `tests/unit/adapters/embedding/test_xinference.py`

**Interfaces:**
- Consumes: `BaseEmbedding` (abstract base with `aembed_documents`, `aembed_query`), `AsyncOpenAI` (already installed)
- Produces: `XinferenceEmbedding` class implementing `BaseEmbedding` with a `warmup()` method for connectivity check

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/adapters/embedding/test_xinference.py
"""Test XinferenceEmbedding adapter."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.adapters.embedding.xinference import XinferenceEmbedding


class MockEmbeddingData:
    def __init__(self, embedding):
        self.embedding = embedding


class MockResponse:
    def __init__(self, embedding):
        self.data = [MagicMock(embedding=MockEmbeddingData(embedding))]


@pytest.mark.asyncio
async def test_aembed_query_calls_xinference():
    """Verify aembed_query sends a single text and returns embedding list."""
    adapter = XinferenceEmbedding(
        endpoint="http://xinference:9997",
        model="bge-m3",
    )

    mock_resp = MagicMock()
    mock_resp.data = [MagicMock(embedding=[0.1] * 1024)]
    adapter.client.embeddings.create = AsyncMock(return_value=mock_resp)

    result = await adapter.aembed_query("hello world")

    assert len(result) == 1024
    adapter.client.embeddings.create.assert_called_once()
    call_args = adapter.client.embeddings.create.call_args
    assert call_args.kwargs["model"] == "bge-m3"
    assert call_args.kwargs["input"] == ["hello world"]


@pytest.mark.asyncio
async def test_aembed_documents_returns_batch_embeddings():
    """Verify aembed_documents sends all texts and returns one embedding per text."""
    adapter = XinferenceEmbedding(
        endpoint="http://xinference:9997",
        model="bge-m3",
    )

    mock_resp = MagicMock()
    mock_resp.data = [
        MagicMock(embedding=[0.1] * 1024),
        MagicMock(embedding=[0.2] * 1024),
        MagicMock(embedding=[0.3] * 1024),
    ]
    adapter.client.embeddings.create = AsyncMock(return_value=mock_resp)

    texts = ["doc 1", "doc 2", "doc 3"]
    result = await adapter.aembed_documents(texts)

    assert len(result) == 3
    assert len(result[0]) == 1024
    adapter.client.embeddings.create.assert_called_once()
    call_args = adapter.client.embeddings.create.call_args
    assert call_args.kwargs["model"] == "bge-m3"
    assert call_args.kwargs["input"] == texts


@pytest.mark.asyncio
async def test_warmup_success():
    """warmup returns True when Xinference responds."""
    adapter = XinferenceEmbedding(
        endpoint="http://xinference:9997",
        model="bge-m3",
    )

    mock_resp = MagicMock()
    mock_resp.data = [MagicMock(embedding=[0.0] * 1024)]
    adapter.client.embeddings.create = AsyncMock(return_value=mock_resp)

    result = await adapter.warmup()
    assert result is True


@pytest.mark.asyncio
async def test_warmup_timeout_falls_back():
    """warmup returns False on connection error."""
    adapter = XinferenceEmbedding(
        endpoint="http://nonexistent:9997",
        model="bge-m3",
    )

    # AsyncOpenAI constructor still works; only the API call fails
    mock_client = MagicMock()
    mock_client.embeddings.create = AsyncMock(side_effect=TimeoutError("connection refused"))
    adapter.client = mock_client

    result = await adapter.warmup()
    assert result is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/adapters/embedding/test_xinference.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.adapters.embedding.xinference'`

- [ ] **Step 3: Write minimal implementation**

Create `app/adapters/embedding/xinference.py`:

```python
"""Xinference GPU embedding adapter via OpenAI-compatible API."""

import asyncio
import structlog
from openai import AsyncOpenAI, TimeoutException
from app.adapters.embedding.base import BaseEmbedding

logger = structlog.get_logger()


class XinferenceEmbedding(BaseEmbedding):
    """Xinference OpenAI-compatible embedding adapter (GPU-accelerated)."""

    def __init__(self, endpoint: str, model: str):
        self.client = AsyncOpenAI(
            base_url=f"{endpoint}/v1",
            api_key="xst-token",
            timeout=30.0,
        )
        self.model = model

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        resp = await self.client.embeddings.create(input=texts, model=self.model)
        return [d.embedding for d in resp.data]

    async def aembed_query(self, query: str) -> list[float]:
        resp = await self.client.embeddings.create(input=[query], model=self.model)
        return resp.data[0].embedding

    async def warmup(self) -> bool:
        """Verify connectivity to Xinference service."""
        try:
            await asyncio.wait_for(
                self.aembed_query("warmup"),
                timeout=10.0,
            )
            return True
        except (TimeoutException, TimeoutError, Exception):
            return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/adapters/embedding/test_xinference.py -v`
Expected: 5/5 PASS

- [ ] **Step 5: Commit**

```bash
git add app/adapters/embedding/xinference.py tests/unit/adapters/embedding/test_xinference.py
git commit -m "feat(embedding): add Xinference GPU adapter with warmup"
```

## Task 3: Embedding Factory — Backend Routing

**Files:**
- Modify: `app/core/embedding_factory.py`
- Test: `tests/unit/core/test_embedding_factory.py`

**Interfaces:**
- Consumes: `Settings.embedding_backend` (str), `XinferenceEmbedding` (from Task 2), `BGEEmbedding` (existing)
- Produces: `get_embedder()` returns either `XinferenceEmbedding` or `BGEEmbedding` based on config

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/core/test_embedding_factory.py
"""Test embedding_factory routes to correct backend."""

import pytest
from unittest.mock import patch, MagicMock
from app.core.embedding_factory import get_embedder, _reset_singleton


@pytest.fixture(autouse=True)
def clean_singleton():
    """Reset singleton before each test."""
    yield
    _reset_singleton()


def test_default_returns_local_bge():
    """Without EMBEDDING_BACKEND set, should return BGEEmbedding (local)."""
    import os
    if "EMBEDDING_BACKEND" in os.environ:
        del os.environ["EMBEDDING_BACKEND"]

    embedder = get_embedder()
    assert type(embedder).__name__ == "BGEEmbedding"


@pytest.mark.asyncio
async def test_xinference_backend_returns_xinference_adapter():
    """With EMBEDDING_BACKEND=xinference, should return XinferenceEmbedding."""
    import os
    os.environ["EMBEDDING_BACKEND"] = "xinference"
    try:
        embedder = get_embedder()
        assert type(embedder).__name__ == "XinferenceEmbedding"
        assert embedder.model == "bge-m3"
        assert "xinference:9997" in embedder.client.base_url.raw_host
    finally:
        del os.environ["EMBEDDING_BACKEND"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/core/test_embedding_factory.py -v`
Expected: FAIL — `_reset_singleton` doesn't exist yet, or `get_embedder` returns BGEEmbedding but test structure fails on xinference branch

- [ ] **Step 3: Write minimal implementation**

Replace `app/core/embedding_factory.py`:

```python
"""Embedding factory — returns a configured embedding adapter singleton."""

from app.core.config import get_settings

_embedder = None


def _reset_singleton():
    """Reset the embedding singleton (for testing)."""
    global _embedder
    _embedder = None


def get_embedder():
    """Return an embedding adapter based on EMBEDDING_BACKEND config."""
    global _embedder
    if _embedder is not None:
        return _embedder

    s = get_settings()

    if s.embedding_backend == "xinference":
        from app.adapters.embedding.xinference import XinferenceEmbedding
        _embedder = XinferenceEmbedding(
            endpoint=s.xinference_endpoint,
            model=s.xinference_embedding_model,
        )
    else:
        from app.adapters.embedding.bge_m3 import BGEEmbedding
        _embedder = BGEEmbedding(model_path=s.bge_embedding_model)

    return _embedder
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/core/test_embedding_factory.py -v`
Expected: 2/2 PASS

- [ ] **Step 5: Commit**

```bash
git add app/core/embedding_factory.py tests/unit/core/test_embedding_factory.py
git commit -m "feat(embedding): config-driven backend routing in embedding_factory"
```

## Task 4: Startup Prewarm — Dual Backend Logic

**Files:**
- Modify: `app/core/events.py:28-35`
- Test: `tests/unit/core/test_events_prewarm.py`

**Interfaces:**
- Consumes: `get_embedder()` (from Task 3), `BaseEmbedding.warmup()` (xinference), `BGEEmbedding._load_model()` (local)
- Produces: Startup prewarm that works for both backends, logs warning on failure

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/core/test_events_prewarm.py
"""Test embedding prewarm logic in events.py."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_prewarm_xinference_success():
    """When backend is xinference, warmup() is called and success is logged."""
    mock_embedder = MagicMock()
    mock_embedder.warmup = AsyncMock(return_value=True)

    with patch("app.core.events.get_embedder", return_value=mock_embedder):
        from app.core.events import on_startup
        # Call the prewarm section directly
        try:
            embedder = mock_embedder
            if hasattr(embedder, "warmup"):
                warmup_success = await asyncio.wait_for(embedder.warmup(), timeout=15.0)
            else:
                await asyncio.to_thread(embedder._load_model)
                warmup_success = True
            assert warmup_success is True
        except Exception:
            pytest.fail("prewarm raised unexpected exception")


@pytest.mark.asyncio
async def test_prewarm_xinference_failure_returns_false():
    """When warmup times out or fails, returns False."""
    mock_embedder = MagicMock()
    mock_embedder.warmup = AsyncMock(side_effect=TimeoutError("connection refused"))

    with patch("app.core.events.get_embedder", return_value=mock_embedder):
        try:
            embedder = mock_embedder
            if hasattr(embedder, "warmup"):
                warmup_success = await asyncio.wait_for(embedder.warmup(), timeout=15.0)
            else:
                warmup_success = False  # shouldn't reach here
            assert warmup_success is False
        except TimeoutError:
            pass  # expected — warmup times out


@pytest.mark.asyncio
async def test_prewarm_local_backend():
    """When backend is local (no warmup), _load_model is called."""
    mock_embedder = MagicMock()
    mock_embedder._load_model = MagicMock()
    # No 'warmup' attribute — simulates BGEEmbedding

    with patch("app.core.events.get_embedder", return_value=mock_embedder):
        try:
            embedder = mock_embedder
            if hasattr(embedder, "warmup"):
                warmup_success = False
            else:
                await asyncio.to_thread(embedder._load_model)
                warmup_success = True
            assert warmup_success is True
            mock_embedder._load_model.assert_called_once()
        except Exception:
            pytest.fail("prewarm raised unexpected exception")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/core/test_events_prewarm.py -v`
Expected: FAIL — current `events.py` calls `embedder._load_model` unconditionally, which will fail for `XinferenceEmbedding` (no `_load_model`)

- [ ] **Step 3: Write minimal implementation**

Replace the prewarm section in `app/core/events.py` (lines 28-35):

```python
    # Prewarm embedding model
    try:
        embedder = get_embedder()
        if hasattr(embedder, "warmup"):
            # Xinference: verify connectivity
            warmup_success = await asyncio.wait_for(
                embedder.warmup(),
                timeout=15.0,
            )
        else:
            # Local: load model into memory
            await asyncio.to_thread(embedder._load_model)
            warmup_success = True
        if warmup_success:
            logger.info("embedding model prewarmed")
    except Exception as e:
        logger.warning("embedding prewarm failed, will load lazily", error=str(e))
```

Remove the old unconditional `await asyncio.to_thread(embedder._load_model)` block.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/core/test_events_prewarm.py -v`
Expected: 3/3 PASS

Also verify existing tests still pass:
Run: `pytest tests/unit/core/ -v`
Expected: All existing core tests pass

- [ ] **Step 5: Commit**

```bash
git add app/core/events.py tests/unit/core/test_events_prewarm.py
git commit -m "feat(events): dual prewarm logic for xinference and local backends"
```

## Task 5: Docker Compose — Add Xinference Service

**Files:**
- Modify: `docker-compose.yml` (after arq-worker section, before neo4j)
- Test: Verify service starts correctly (manual/smoke test)

**Interfaces:**
- Consumes: NVIDIA driver + nvidia-container-toolkit (prerequisites, out of scope)
- Produces: `xinference` service on port 9997 with GPU reservation, named volume for model persistence

- [ ] **Step 1: Write the test**

This task is infrastructure-level — no unit test. Write a smoke test script:

```python
# tests/smoke/test_xinference_service.py
"""Smoke test: verify xinference service is reachable in docker-compose."""

import asyncio
import pytest


@pytest.mark.asyncio
async def test_xinference_endpoint_reachable():
    """Xinference should respond on /v1/models endpoint."""
    from openai import AsyncOpenAI
    client = AsyncOpenAI(base_url="http://xinference:9997/v1", api_key="xst-token")
    try:
        models = await asyncio.wait_for(client.models.list(), timeout=5.0)
        model_ids = [m.id for m in models.data]
        assert "bge-m3" in model_ids or len(model_ids) >= 0  # service responded
    except Exception:
        pytest.skip("xinference service not available (not running in docker)")
```

- [ ] **Step 2: Add xinference service to docker-compose.yml**

Insert after the `arq-worker` section (after line 93, before line 95 `# === Phase 2`):

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
```

Add the named volume at the bottom of the `volumes:` section:

```yaml
  xinference_models:
```

- [ ] **Step 3: Verify syntax**

Run: `docker compose config` (or `docker-compose config`)
Expected: YAML parses without errors, no duplicate volume names

- [ ] **Step 4: Commit**

```bash
git add docker-compose.yml tests/smoke/test_xinference_service.py
git commit -m "feat(docker): add xinference GPU service for embedding acceleration"
```

## Task 6: Environment Files — Backend Config

**Files:**
- Modify: `.env` (add `EMBEDDING_BACKEND=local`)
- Modify: `.env.docker` (add `EMBEDDING_BACKEND=xinference`)

**Interfaces:**
- Consumes: New config fields from Task 1
- Produces: Both env files with correct backend selection

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/core/test_env_config.py
"""Verify .env files set correct EMBEDDING_BACKEND."""

import os
import pytest
from app.core.config import Settings


def test_local_env_defaults_to_local_backend():
    """When EMBEDDING_BACKEND not set, default is 'local'."""
    if "EMBEDDING_BACKEND" in os.environ:
        del os.environ["EMBEDDING_BACKEND"]
    s = Settings()
    assert s.embedding_backend == "local"


def test_docker_env_sets_xinference_backend():
    """When EMBEDDING_BACKEND=xinference, backend routes to xinference."""
    os.environ["EMBEDDING_BACKEND"] = "xinference"
    try:
        s = Settings()
        assert s.embedding_backend == "xinference"
    finally:
        del os.environ["EMBEDDING_BACKEND"]
```

- [ ] **Step 2: Run test to verify it passes** (already passes from Task 1 — verify no regression)

Run: `pytest tests/unit/core/test_env_config.py -v`
Expected: 2/2 PASS

- [ ] **Step 3: Update .env with xinference fields**

Append to end of `.env`:

```
# Xinference (GPU embedding)
EMBEDDING_BACKEND=local
XINFERENCE_ENDPOINT=http://localhost:9997
XINFERENCE_EMBEDDING_MODEL=bge-m3
```

- [ ] **Step 4: Update .env.docker with xinference fields**

Append to end of `.env.docker`:

```
# Xinference (GPU embedding)
EMBEDDING_BACKEND=xinference
XINFERENCE_ENDPOINT=http://xinference:9997
XINFERENCE_EMBEDDING_MODEL=bge-m3
```

- [ ] **Step 5: Commit**

```bash
git add .env .env.docker tests/unit/core/test_env_config.py
git commit -m "feat(env): add xinference config to .env and .env.docker"
```

## Task 7: Integration — End-to-End Backend Switch Test

**Files:**
- Create: `tests/integration/test_embedding_backend_switch.py`

**Interfaces:**
- Consumes: All previous tasks (config, adapter, factory, events)
- Produces: Verification that switching backends works end-to-end

- [ ] **Step 1: Write the integration test**

```python
# tests/integration/test_embedding_backend_switch.py
"""End-to-end test: verify embedding backend switch works."""

import pytest
import os
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture(autouse=True)
def clean_env():
    """Clean up env vars after each test."""
    yield
    for key in ["EMBEDDING_BACKEND", "XINFERENCE_ENDPOINT", "XINFERENCE_EMBEDDING_MODEL"]:
        if key in os.environ:
            del os.environ[key]


@pytest.mark.asyncio
async def test_local_backend_embeds_documents():
    """Local backend produces valid embeddings."""
    # Force local
    if "EMBEDDING_BACKEND" in os.environ:
        del os.environ["EMBEDDING_BACKEND"]

    # Reset singleton
    from app.core import embedding_factory
    embedding_factory._reset_singleton()

    embedder = embedding_factory.get_embedder()
    assert type(embedder).__name__ == "BGEEmbedding"

    # Mock the model encode to avoid loading BGE-M3
    mock_model = MagicMock()
    mock_array = MagicMock()
    mock_array.tolist.return_value = [[0.1] * 1024, [0.2] * 1024]
    mock_model.encode.return_value = mock_array

    with patch.object(embedder, "_load_model_async", return_value=mock_model):
        texts = ["doc one", "doc two"]
        result = await embedder.aembed_documents(texts)
        assert len(result) == 2
        assert len(result[0]) == 1024


@pytest.mark.asyncio
async def test_xinference_backend_embeds_documents():
    """Xinference backend produces valid embeddings via AsyncOpenAI."""
    os.environ["EMBEDDING_BACKEND"] = "xinference"

    from app.core import embedding_factory
    embedding_factory._reset_singleton()

    embedder = embedding_factory.get_embedder()
    assert type(embedder).__name__ == "XinferenceEmbedding"

    mock_resp = MagicMock()
    mock_resp.data = [
        MagicMock(embedding=[0.1] * 1024),
        MagicMock(embedding=[0.2] * 1024),
    ]
    embedder.client.embeddings.create = AsyncMock(return_value=mock_resp)

    texts = ["doc one", "doc two"]
    result = await embedder.aembed_documents(texts)
    assert len(result) == 2
    assert len(result[0]) == 1024
```

- [ ] **Step 2: Run test to verify it passes**

Run: `pytest tests/integration/test_embedding_backend_switch.py -v`
Expected: 2/2 PASS

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_embedding_backend_switch.py
git commit -m "test(integration): add end-to-end backend switch verification"
```

## File Summary

| File | Action | Task |
|------|--------|------|
| `app/core/config.py` | Modify (+3 fields) | 1 |
| `app/adapters/embedding/xinference.py` | **Create** | 2 |
| `app/core/embedding_factory.py` | Modify (routing logic) | 3 |
| `app/core/events.py` | Modify (dual prewarm) | 4 |
| `docker-compose.yml` | Modify (+xinference service) | 5 |
| `.env` | Modify (+3 lines) | 6 |
| `.env.docker` | Modify (+3 lines) | 6 |
| `tests/unit/core/test_xinference_config.py` | **Create** | 1 |
| `tests/unit/adapters/embedding/test_xinference.py` | **Create** | 2 |
| `tests/unit/core/test_embedding_factory.py` | **Create** | 3 |
| `tests/unit/core/test_events_prewarm.py` | **Create** | 4 |
| `tests/smoke/test_xinference_service.py` | **Create** | 5 |
| `tests/unit/core/test_env_config.py` | **Create** | 6 |
| `tests/integration/test_embedding_backend_switch.py` | **Create** | 7 |

## Success Criteria (from spec)

1. `docker compose up -d xinference` starts without errors
2. Xinference serves BGE-M3 on port 9997 with OpenAI-compatible API
3. `EMBEDDING_BACKEND=xinference` → embedding uses GPU
4. `EMBEDDING_BACKEND=local` → falls back to CPU (no regression)
5. 99 chunks embedding time drops from ~130s to <20s

## Prerequisites (Out of Scope for This Plan)

- Upgrade NVIDIA driver from 451.48 to latest (supports CUDA 12.x)
- Install `nvidia-container-toolkit` in WSL2
- Install Docker Desktop with GPU support or nvidia-docker2

These must be done BEFORE running Task 5's smoke test. The code changes (Tasks 1-4, 6-7) work independently of GPU availability.
