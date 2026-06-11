"""Test BGE reranker with mocked FlagEmbedding."""

import pytest


class _FakeFlagReranker:
    def __init__(self, model_name, use_fp16=True):
        self.model_name = model_name
        self.use_fp16 = use_fp16

    def compute_score(self, pairs):
        # Return higher scores for pairs whose doc text contains the query
        return [1.0 if pair[0] in pair[1] else 0.1 for pair in pairs]


@pytest.fixture(autouse=True)
def mock_flagemebedding(monkeypatch):
    """Replace FlagEmbedding.FlagReranker with fake."""
    import sys
    fake_module = type(sys)("FlagEmbedding")
    fake_module.FlagReranker = _FakeFlagReranker
    monkeypatch.setitem(sys.modules, "FlagEmbedding", fake_module)


class TestBGEReranker:
    async def test_scores_documents(self):
        from app.adapters.reranker.bge import BGEReranker
        bge = BGEReranker()
        docs = [
            {"chunk_id": "a", "text": "this matches query", "score": 0.5,
             "source": "milvus", "_tool": "semantic_search"},
            {"chunk_id": "b", "text": "no match here", "score": 0.5,
             "source": "milvus", "_tool": "semantic_search"},
        ]
        result = await bge.rerank("query", docs)
        # doc "a" has higher relevance because text contains "query"
        assert result[0]["chunk_id"] == "a"
        assert "_rerank_score" in result[0]

    async def test_empty_input(self):
        from app.adapters.reranker.bge import BGEReranker
        bge = BGEReranker()
        result = await bge.rerank("query", [])
        assert result == []

    async def test_top_k_truncation(self):
        from app.adapters.reranker.bge import BGEReranker
        bge = BGEReranker()
        docs = [
            {"chunk_id": f"d{i}", "text": f"text {i}", "score": float(10 - i),
             "source": "milvus", "_tool": "semantic_search"}
            for i in range(10)
        ]
        result = await bge.rerank("whatever", docs, top_k=3)
        assert len(result) == 3

    async def test_single_document_handles_scalar_score(self):
        """compute_score returns a float for a single pair, not a list."""
        from app.adapters.reranker.bge import BGEReranker
        bge = BGEReranker()
        docs = [{"chunk_id": "solo", "text": "only one", "score": 0.8,
                 "source": "milvus", "_tool": "semantic_search"}]
        result = await bge.rerank("query", docs)
        assert len(result) == 1
        assert result[0]["chunk_id"] == "solo"

    async def test_lazy_model_init(self):
        """Model is not loaded until first rerank call."""
        from app.adapters.reranker.bge import BGEReranker
        bge = BGEReranker()
        assert bge._model is None
        docs = [{"chunk_id": "a", "text": "text", "score": 1.0,
                 "source": "milvus", "_tool": "semantic_search"}]
        await bge.rerank("q", docs)
        assert bge._model is not None