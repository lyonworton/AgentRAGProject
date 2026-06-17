"""BGE-M3 Embedding — local dense embedding via sentence-transformers.

Uses BAAI/bge-m3 loaded from local disk via HF_HOME or direct path.
Model outputs 1024-dim embeddings.

BAAI/bge-m3 supports:
  - Dense retrieval (1024-dim)
  - Sparse retrieval (BM25-like)
  - Multi-vector (ColBERT)

This adapter uses dense retrieval mode.
"""

import asyncio
import structlog
from app.adapters.embedding.base import BaseEmbedding
from app.core.config import get_settings

logger = structlog.get_logger()
settings = get_settings()


class BGEEmbedding(BaseEmbedding):
    """BGE-M3 dense embedding adapter.

    Args:
        model_path: Path to the BGE-M3 model directory.
    """

    _model = None
    _model_path: str = None
    _initialized = False
    _loading_lock = None

    def __init__(self, model_path: str = None):
        BGEEmbedding._model_path = model_path or settings.bge_embedding_model

    def _load_model_sync(self):
        """Load model synchronously (must run in a thread pool)."""
        from sentence_transformers import SentenceTransformer

        logger.info("loading embedding model", model=self._model_path)
        BGEEmbedding._model = SentenceTransformer(
            self._model_path,
            device="cuda" if settings.use_gpu else "cpu",
        )
        BGEEmbedding._initialized = True
        logger.info("embedding model loaded", model=self._model_path)
        return BGEEmbedding._model

    def _load_model(self):
        """Get the loaded model, loading if necessary (blocks caller thread)."""
        if BGEEmbedding._initialized:
            return BGEEmbedding._model
        return self._load_model_sync()

    async def _load_model_async(self):
        """Load model without blocking the event loop."""
        if BGEEmbedding._initialized:
            return BGEEmbedding._model
        if BGEEmbedding._loading_lock is None:
            BGEEmbedding._loading_lock = asyncio.Lock()
        async with BGEEmbedding._loading_lock:
            if BGEEmbedding._initialized:
                return BGEEmbedding._model
            return await asyncio.to_thread(self._load_model_sync)

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        model = await self._load_model_async()

        def _encode():
            return model.encode(
                texts,
                normalize_embeddings=True,
                batch_size=256,
                show_progress_bar=False,
            )

        # CPU-bound: run in thread pool to avoid blocking the event loop.
        # 600s timeout: BGE-M3 on CPU is slow (~10s cold start + ~1s per 32 chunks).
        result = await asyncio.wait_for(asyncio.to_thread(_encode), timeout=600.0)
        return result.tolist()

    async def aembed_query(self, query: str) -> list[float]:
        model = await self._load_model_async()

        def _encode():
            emb = model.encode(
                [query],
                normalize_embeddings=True,
            )
            return emb[0]

        # Single query embedding is fast (<1s), but keep consistent timeout.
        result = await asyncio.wait_for(asyncio.to_thread(_encode), timeout=60.0)
        return result.tolist()

    @classmethod
    def reset(cls):
        """Reset singleton state (for testing)."""
        cls._model = None
        cls._model_path = None
        cls._initialized = False