"""Test Cohere reranker with mocked client."""

import pytest


class _FakeRerankResult:
    def __init__(self, results):
        self.results = results


class _FakeRerankResultItem:
    def __init__(self, index, relevance_score):
        self.index = index
        self.relevance_score = relevance_score


class _FakeCohereClient:
    def __init__(self, api_key):
        self.api_key = api_key

    def rerank(self, query, documents, model, top_n):
        # Return reordered: doc containing query gets high score
        items = []
        for i, doc in enumerate(documents):
            score = 0.95 if query in doc else 0.05
            items.append(_FakeRerankResultItem(i, score))
        return _FakeRerankResult(items)


@pytest.fixture(autouse=True)
def mock_cohere(monkeypatch):
    import sys
    fake_module = type(sys)("cohere")
    fake_module.Client = _FakeCohereClient
    monkeypatch.setitem(sys.modules, "cohere", fake_module)


class TestCohereReranker:
    async def test_scores_documents(self):
        from app.adapters.reranker.cohere import CohereReranker
        cr = CohereReranker(api_key="test-key")
        docs = [
            {"chunk_id": "a", "text": "this has query in it", "score": 0.5,
             "source": "milvus", "_tool": "semantic_search"},
            {"chunk_id": "b", "text": "no match", "score": 0.5,
             "source": "milvus", "_tool": "semantic_search"},
        ]
        result = await cr.rerank("query", docs)
        assert result[0]["chunk_id"] == "a"
        assert "_rerank_score" in result[0]

    async def test_empty_input(self):
        from app.adapters.reranker.cohere import CohereReranker
        cr = CohereReranker(api_key="test-key")
        result = await cr.rerank("query", [])
        assert result == []

    async def test_top_k_truncation(self):
        from app.adapters.reranker.cohere import CohereReranker
        cr = CohereReranker(api_key="test-key")
        docs = [
            {"chunk_id": f"d{i}", "text": f"text {i}", "score": float(10 - i),
             "source": "milvus", "_tool": "semantic_search"}
            for i in range(10)
        ]
        result = await cr.rerank("whatever", docs, top_k=3)
        assert len(result) == 3

    async def test_missing_api_key_raises(self):
        from app.adapters.reranker.cohere import CohereReranker
        with pytest.raises(ValueError, match="COHERE_API_KEY"):
            CohereReranker(api_key="")

    async def test_api_error_falls_back(self):
        """If the API call itself fails (not init), return docs unchanged."""
        from app.adapters.reranker.cohere import CohereReranker
        cr = CohereReranker(api_key="test-key")
        # Replace client with one that always fails
        class _BrokenClient:
            def rerank(self, *a, **kw):
                raise RuntimeError("API down")
        cr._client = _BrokenClient()

        docs = [{"chunk_id": "a", "text": "text", "score": 0.8,
                 "source": "milvus", "_tool": "semantic_search"}]
        result = await cr.rerank("query", docs)
        assert len(result) == 1
        assert result[0]["chunk_id"] == "a"