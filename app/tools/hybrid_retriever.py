"""Hybrid retriever — BM25 (Elasticsearch) + Dense (BGE-M3 / Milvus) → RRF fusion → BGE-Reranker.

Pipeline:
  Query
    ├── BM25 (ES)         → top_K candidates
    └── Dense (Milvus)    → top_K candidates
              ↓
        RRF fusion (k=60) → merged top_M
              ↓
    BGE-Reranker (cross-encoder) → final ranked top_N
"""

import asyncio
import structlog
from app.adapters.reranker.rrf import RRFReranker
from app.adapters.reranker.bge import BGEReranker
from app.core.embedding_factory import get_embedder
from app.adapters.search.elasticsearch import ElasticsearchStore
from app.adapters.vector_store.milvus import MilvusStore
from app.core.config import get_settings

logger = structlog.get_logger()
settings = get_settings()


class HybridRetriever:
    """BM25 + Dense hybrid retrieval with RRF fusion and optional BGE re-ranking.

    Args:
        bm25_top_k: Candidates from ES.
        dense_top_k: Candidates from Milvus.
        rrf_top_k:  Top-K after RRF fusion (before re-ranking).
        bge_top_k:  Final top-K after BGE cross-encoder re-ranking.
        use_bge_rerank: Whether to apply BGE re-ranking after RRF fusion.
    """

    def __init__(
        self,
        bm25_top_k: int = 20,
        dense_top_k: int = 20,
        rrf_top_k: int = 20,
        bge_top_k: int = 10,
        use_bge_rerank: bool = True,
    ):
        self._bm25_top_k = bm25_top_k
        self._dense_top_k = dense_top_k
        self._rrf_top_k = rrf_top_k
        self._bge_top_k = bge_top_k
        self._use_bge_rerank = use_bge_rerank

    async def retrieve(
        self,
        query: str,
        collection_ids: list[str],
    ) -> list[dict]:
        """Execute hybrid retrieval.

        Returns sorted list of hit dicts with _rerank_score.
        """
        if not collection_ids:
            return []

        # Run BM25 and Dense in parallel
        bm25_hits, dense_hits = await asyncio.gather(
            self._bm25_search(query, collection_ids),
            self._dense_search(query, collection_ids),
        )

        # Tag and merge
        all_hits = []
        for h in bm25_hits:
            h["_tool"] = "keyword_search"
            all_hits.append(h)
        for h in dense_hits:
            h["_tool"] = "semantic_search"
            all_hits.append(h)

        if not all_hits:
            return []

        # Stage 1: RRF fusion
        rrf = RRFReranker(k=settings.rrf_k)
        fused = await rrf.rerank(query, all_hits, self._rrf_top_k)

        # Stage 2: BGE cross-encoder re-ranking
        if self._use_bge_rerank:
            try:
                bge = BGEReranker(model_name=settings.reranker_model)
                fused = await bge.rerank(query, fused, self._bge_top_k)
            except Exception:
                logger.warning("bge_rerank_failed_falling_back_to_rrf", exc_info=True)

        return fused

    async def _bm25_search(
        self, query: str, collection_ids: list[str]
    ) -> list[dict]:
        es = ElasticsearchStore()
        results: list[dict] = []
        for col_id in collection_ids:
            try:
                hits = await es.asearch(col_id, query, top_k=self._bm25_top_k)
                for h in hits:
                    text = h["text"]
                    if len(text) > 500:
                        text = text[:500] + "..."
                    results.append({
                        "chunk_id": h["document_id"],
                        "document_id": h["document_id"],
                        "text": text,
                        "score": h["score"],
                        "source": "keyword",
                    })
            except Exception:
                continue
        return results

    async def _dense_search(
        self, query: str, collection_ids: list[str]
    ) -> list[dict]:
        embedder = get_embedder()
        store = MilvusStore()
        qe = await embedder.aembed_query(query)

        results: list[dict] = []
        seen = set()
        for col_id in collection_ids:
            col_name = f"col_{col_id}"
            try:
                hits = await store.search(col_name, qe, top_k=self._dense_top_k)
                for hit in hits:
                    if hit.chunk_id not in seen:
                        results.append({
                            "chunk_id": hit.chunk_id,
                            "document_id": hit.document_id,
                            "text": hit.text,
                            "score": hit.score,
                            "source": "milvus",
                        })
                        seen.add(hit.chunk_id)
            except Exception:
                continue
        return results