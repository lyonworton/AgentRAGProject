"""Reciprocal Rank Fusion — zero-cost cross-source score normalization.

RRF_score(doc) = Σ 1/(k + rank_in_source(doc))

Documents are grouped by _tool tag, ranked within each group by original score,
then fused via the RRF formula. This fixes the problem where Milvus cosine scores,
ES BM25 scores, and KG fixed scores are not directly comparable.
"""

from app.adapters.reranker.base import BaseReranker


class RRFReranker(BaseReranker):
    """Reciprocal Rank Fusion re-ranker.

    Args:
        k: RRF constant (default 60). Higher values dampen rank differences.
           Standard value from the literature is 60.
    """

    def __init__(self, k: int = 60):
        self._k = k

    async def rerank(
        self, query: str, documents: list[dict], top_k: int = 10
    ) -> list[dict]:
        if not documents:
            return []

        # 1. Group by _tool source
        groups: dict[str, list[dict]] = {}
        for doc in documents:
            tool = doc.get("_tool", "unknown")
            groups.setdefault(tool, []).append(doc)

        # 2. Sort each group by original score descending
        for docs in groups.values():
            docs.sort(key=lambda d: d.get("score", 0), reverse=True)

        # 3. Compute RRF score for each document
        for doc in documents:
            doc["_rrf_score"] = 0.0

        for docs in groups.values():
            for rank_idx, doc in enumerate(docs):
                doc["_rrf_score"] += 1.0 / (self._k + rank_idx + 1)

        # 4. Sort by RRF score descending, return top_k
        documents.sort(key=lambda d: d.get("_rrf_score", 0), reverse=True)
        for doc in documents:
            doc["_rerank_score"] = doc.pop("_rrf_score")

        return documents[:top_k]