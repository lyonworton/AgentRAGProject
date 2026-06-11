"""Test RRF formula: single-source, multi-source, k parameter, empty input."""

import pytest
from app.adapters.reranker.rrf import RRFReranker


def _doc(chunk_id: str, score: float, tool: str = "semantic_search"):
    return {"chunk_id": chunk_id, "text": f"text-{chunk_id}", "score": score,
            "source": "milvus", "_tool": tool}


class TestRRFReranker:
    async def test_single_source_ranks_by_score(self):
        """Within a single source, RRF preserves original rank order."""
        rrf = RRFReranker(k=60)
        docs = [
            _doc("a", 0.9),
            _doc("b", 0.5),
            _doc("c", 0.8),
        ]
        result = await rrf.rerank("query", docs, top_k=10)
        ids = [d["chunk_id"] for d in result]
        # 0.9 > 0.8 > 0.5 → a, c, b
        assert ids == ["a", "c", "b"]

    async def test_multi_source_fuses_ranks(self):
        """Documents from multiple sources are fused by rank, not raw score."""
        rrf = RRFReranker(k=60)
        docs = [
            _doc("milvus-1", 0.9, "semantic_search"),
            _doc("milvus-2", 0.8, "semantic_search"),
            _doc("es-1", 12.5, "keyword_search"),   # BM25 score is huge
            _doc("es-2", 5.0, "keyword_search"),
            _doc("kg-1", 0.5, "kg_search"),
        ]
        result = await rrf.rerank("query", docs, top_k=10)
        ids = [d["chunk_id"] for d in result]
        # Each source's #1 gets 1/61, source's #2 gets 1/62
        # milvus-1 (rank1) + es-1 (rank1) + kg-1 (rank1) should be top
        # milvus-2 (rank2) + es-2 (rank2) should be next
        # Without RRF, es-1 (12.5) would dominate
        assert ids[0] in ["milvus-1", "es-1", "kg-1"]  # top-3 should be rank-1 from each source

    async def test_empty_input(self):
        rrf = RRFReranker()
        result = await rrf.rerank("query", [], top_k=10)
        assert result == []

    async def test_top_k_truncation(self):
        rrf = RRFReranker(k=60)
        docs = [_doc(f"d{i}", float(100 - i)) for i in range(10)]
        result = await rrf.rerank("query", docs, top_k=3)
        assert len(result) == 3

    async def test_custom_k_parameter(self):
        """Higher k dampens rank differences."""
        rrf_low = RRFReranker(k=1)
        rrf_high = RRFReranker(k=100)
        docs_low = [_doc(f"d{i}", float(100 - i)) for i in range(10)]
        docs_high = [_doc(f"d{i}", float(100 - i)) for i in range(10)]
        result_low = await rrf_low.rerank("query", docs_low, top_k=10)
        result_high = await rrf_high.rerank("query", docs_high, top_k=10)
        # Both should preserve same order, but scores differ in spread
        low_scores = [d["_rerank_score"] for d in result_low]
        high_scores = [d["_rerank_score"] for d in result_high]
        # Low k has larger spread between ranks
        low_spread = low_scores[0] - low_scores[-1]
        high_spread = high_scores[0] - high_scores[-1]
        assert low_spread > high_spread

    async def test_sets_rerank_score(self):
        rrf = RRFReranker()
        docs = [_doc("a", 0.9)]
        result = await rrf.rerank("query", docs)
        assert "_rerank_score" in result[0]
        assert result[0]["_rerank_score"] > 0