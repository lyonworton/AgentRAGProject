import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.tools.semantic_search import SemanticSearchTool


@pytest.mark.asyncio
async def test_semantic_search_returns_unified_format():
    tool = SemanticSearchTool()
    assert tool.name == "semantic_search"
    assert "Milvus" in tool.description

    with patch("app.tools.semantic_search.OpenAIEmbedding") as mock_emb, \
         patch("app.tools.semantic_search.MilvusStore") as mock_store, \
         patch("app.tools.semantic_search.OpenAILLM") as mock_llm:

        mock_llm_instance = MagicMock()
        mock_llm_instance.agenerate_structured = AsyncMock(
            return_value=["variant 1", "variant 2", "variant 3"]
        )
        mock_llm.return_value = mock_llm_instance

        mock_emb_instance = MagicMock()
        mock_emb_instance.aembed_query = AsyncMock(return_value=[0.1] * 1536)
        mock_emb.return_value = mock_emb_instance

        from app.adapters.vector_store.base import SearchResult
        mock_store_instance = MagicMock()
        mock_store_instance.search = AsyncMock(return_value=[
            SearchResult(chunk_id="c1", document_id="d1", text="hello world", score=0.95, metadata={})
        ])
        mock_store.return_value = mock_store_instance

        results = await tool.arun("test query", ["col1"])

        assert len(results) > 0
        assert results[0]["chunk_id"] == "c1"
        assert results[0]["document_id"] == "d1"
        assert results[0]["text"] == "hello world"
        assert results[0]["score"] == 0.95
        assert results[0]["source"] == "milvus"


@pytest.mark.asyncio
async def test_semantic_search_deduplicates_by_chunk_id():
    tool = SemanticSearchTool()
    with patch("app.tools.semantic_search.OpenAIEmbedding") as mock_emb, \
         patch("app.tools.semantic_search.MilvusStore") as mock_store, \
         patch("app.tools.semantic_search.OpenAILLM") as mock_llm:

        mock_llm_instance = MagicMock()
        mock_llm_instance.agenerate_structured = AsyncMock(return_value=["v1"])
        mock_llm.return_value = mock_llm_instance

        mock_emb_instance = MagicMock()
        mock_emb_instance.aembed_query = AsyncMock(return_value=[0.1] * 1536)
        mock_emb.return_value = mock_emb_instance

        from app.adapters.vector_store.base import SearchResult
        mock_store_instance = MagicMock()
        mock_store_instance.search = AsyncMock(return_value=[
            SearchResult(chunk_id="c1", document_id="d1", text="text", score=0.9, metadata={}),
            SearchResult(chunk_id="c1", document_id="d1", text="text", score=0.8, metadata={}),
        ])
        mock_store.return_value = mock_store_instance

        results = await tool.arun("test", ["col1"])
        assert len(results) == 1  # deduplicated


@pytest.mark.asyncio
async def test_semantic_search_empty_collections():
    tool = SemanticSearchTool()
    results = await tool.arun("test", [])
    assert results == []


@pytest.mark.asyncio
async def test_semantic_search_expand_queries_failure_uses_original():
    tool = SemanticSearchTool()
    with patch("app.tools.semantic_search.OpenAIEmbedding") as mock_emb, \
         patch("app.tools.semantic_search.MilvusStore") as mock_store, \
         patch("app.tools.semantic_search.OpenAILLM") as mock_llm:

        mock_llm_instance = MagicMock()
        mock_llm_instance.agenerate_structured = AsyncMock(side_effect=Exception("LLM down"))
        mock_llm.return_value = mock_llm_instance

        mock_emb_instance = MagicMock()
        mock_emb_instance.aembed_query = AsyncMock(return_value=[0.1] * 1536)
        mock_emb.return_value = mock_emb_instance

        from app.adapters.vector_store.base import SearchResult
        mock_store_instance = MagicMock()
        mock_store_instance.search = AsyncMock(return_value=[
            SearchResult(chunk_id="c1", document_id="d1", text="text", score=0.9, metadata={})
        ])
        mock_store.return_value = mock_store_instance

        results = await tool.arun("original query", ["col1"])
        assert len(results) == 1  # falls back to original query