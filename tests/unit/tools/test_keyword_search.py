import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.tools.keyword_search import KeywordSearchTool


@pytest.mark.asyncio
async def test_keyword_search_returns_unified_format():
    tool = KeywordSearchTool()
    assert tool.name == "keyword_search"
    assert "Elasticsearch" in tool.description

    with patch("app.tools.keyword_search.ElasticsearchStore") as mock_es:
        mock_instance = MagicMock()
        mock_instance.asearch = AsyncMock(return_value=[
            {"document_id": "doc1", "title": "Title", "text": "Full text content here", "score": 2.5},
        ])
        mock_es.return_value = mock_instance

        results = await tool.arun("test", ["col1"])

        assert len(results) == 1
        assert results[0]["chunk_id"] == "doc1"
        assert results[0]["document_id"] == "doc1"
        assert results[0]["text"] == "Full text content here"
        assert results[0]["score"] == 2.5
        assert results[0]["source"] == "keyword"


@pytest.mark.asyncio
async def test_keyword_search_truncates_long_text():
    tool = KeywordSearchTool()
    long_text = "x" * 1000
    with patch("app.tools.keyword_search.ElasticsearchStore") as mock_es:
        mock_instance = MagicMock()
        mock_instance.asearch = AsyncMock(return_value=[
            {"document_id": "doc1", "title": "T", "text": long_text, "score": 1.0},
        ])
        mock_es.return_value = mock_instance

        results = await tool.arun("test", ["col1"])
        assert len(results[0]["text"]) <= 503  # 500 + "..." at most
        assert results[0]["text"].endswith("...")


@pytest.mark.asyncio
async def test_keyword_search_empty_collections():
    tool = KeywordSearchTool()
    results = await tool.arun("test", [])
    assert results == []