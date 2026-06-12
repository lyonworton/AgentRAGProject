"""BGE Re-ranker — semantic cross-encoder re-ranking via FlagEmbedding.

Uses BAAI/bge-reranker-v2-m3 by default. The model is ~1.5GB and downloaded
on first use. FlagReranker is synchronous; we wrap it with asyncio.to_thread.

Requires: FlagEmbedding>=1.2.0 (optional dependency)
"""

import asyncio
import structlog
from app.adapters.reranker.base import BaseReranker

logger = structlog.get_logger()


class BGEReranker(BaseReranker):
    """BGE-reranker-v2-m3 cross-encoder.

    Args:
        model_name: HuggingFace model identifier.
        use_fp16: Use half-precision for lower memory (~1.5GB vs ~3GB).
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-reranker-v2-m3",
        use_fp16: bool = True,
    ):
        self._model_name = model_name
        self._use_fp16 = use_fp16
        self._model = None  # lazy init

    def _load_model(self):
        if self._model is not None:
            return
        from FlagEmbedding import FlagReranker

        logger.info("loading reranker model", model=self._model_name, fp16=self._use_fp16)
        self._model = FlagReranker(self._model_name, use_fp16=self._use_fp16)
        logger.info("reranker model loaded", model=self._model_name)

    async def rerank(
        self, query: str, documents: list[dict], top_k: int = 10
    ) -> list[dict]:
        if not documents:
            return []

        # Lazy-load model with timeout — FlagReranker.__init__ can hang in PyTorch threads
        if self._model is None:
            try:
                await asyncio.wait_for(
                    asyncio.to_thread(self._load_model),
                    timeout=30.0,
                )
            except (asyncio.TimeoutError, Exception):
                logger.warning(
                    "BGE reranker model load timed out after 30s, "
                    "falling back to original document order"
                )
                documents.sort(key=lambda d: d.get("score", 0), reverse=True)
                return documents[:top_k]

        pairs = [[query, doc["text"]] for doc in documents]
        scores = await asyncio.to_thread(self._model.compute_score, pairs)

        # compute_score returns a float for a single pair, list for multiple
        if isinstance(scores, float):
            scores = [scores]

        for doc, score in zip(documents, scores):
            doc["_rerank_score"] = float(score)

        documents.sort(key=lambda d: d.get("_rerank_score", 0), reverse=True)
        return documents[:top_k]