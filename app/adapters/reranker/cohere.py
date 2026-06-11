"""Cohere Re-ranker — semantic re-ranking via Cohere Rerank API.

Cloud-based, no local model required. Pay-per-use pricing.

Requires: cohere>=5.0.0 (optional dependency)
Environment: COHERE_API_KEY must be set.
"""

import asyncio
import structlog
from app.adapters.reranker.base import BaseReranker

logger = structlog.get_logger()


class CohereReranker(BaseReranker):
    """Cohere Rerank API v3.

    Args:
        api_key: Cohere API key.
        model: Cohere rerank model identifier.
    """

    def __init__(self, api_key: str, model: str = "rerank-english-v3.0"):
        if not api_key:
            raise ValueError("COHERE_API_KEY is required for Cohere reranker")
        import cohere

        self._client = cohere.Client(api_key)
        self._model = model

    async def rerank(
        self, query: str, documents: list[dict], top_k: int = 10
    ) -> list[dict]:
        if not documents:
            return []

        texts = [doc["text"] for doc in documents]

        try:
            response = await asyncio.to_thread(
                self._client.rerank,
                query=query,
                documents=texts,
                model=self._model,
                top_n=top_k,
            )
        except Exception:
            logger.warning("cohere rerank failed, returning input unchanged")
            for doc in documents:
                doc["_rerank_score"] = doc.get("score", 0)
            return documents[:top_k]

        # response.results: [{index: int, relevance_score: float}, ...]
        for r in response.results:
            documents[r.index]["_rerank_score"] = r.relevance_score

        documents.sort(key=lambda d: d.get("_rerank_score", 0), reverse=True)
        return documents[:top_k]