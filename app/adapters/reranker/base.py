from abc import ABC, abstractmethod


class BaseReranker(ABC):
    """Abstract reranker that takes query + documents and returns re-ranked documents.

    Documents are dicts with at minimum: chunk_id, text, score, source, _tool.
    Each implementation adds a _rerank_score field for downstream consumers.
    """

    @abstractmethod
    async def rerank(
        self, query: str, documents: list[dict], top_k: int = 10
    ) -> list[dict]:
        """Re-rank documents by relevance to query.

        Args:
            query: The user's search query.
            documents: List of dicts with chunk_id, text, score, source, _tool.
            top_k: Maximum number of documents to return.

        Returns:
            Re-ranked documents with _rerank_score field added, sorted descending.
        """
        ...


class TwoStageReranker(BaseReranker):
    """Compose two rerankers: stage1 coarse → top_k truncation → stage2 fine.

    Used when provider=bge or provider=cohere:
        stage1 = RRF (always, zero-cost cross-source fusion)
        stage2 = BGE or Cohere (semantic re-ranking on top candidates)
    """

    def __init__(self, stage1: BaseReranker, stage2: BaseReranker, top_k: int):
        self._s1 = stage1
        self._s2 = stage2
        self._top_k = top_k

    async def rerank(
        self, query: str, documents: list[dict], top_k: int = 10
    ) -> list[dict]:
        if not documents:
            return []
        candidates = await self._s1.rerank(query, documents, self._top_k)
        if not candidates:
            return []
        try:
            return await self._s2.rerank(query, candidates, top_k)
        except Exception:
            import structlog
            structlog.get_logger().warning(
                "two_stage_reranker_stage2_failed_falling_back_to_rrf",
                exc_info=True,
            )
            candidates.sort(key=lambda d: d.get("_rerank_score", 0), reverse=True)
            return candidates[:top_k]