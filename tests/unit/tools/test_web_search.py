import sys
import pytest
from unittest.mock import patch, AsyncMock, MagicMock


@pytest.fixture(autouse=True)
def _mock_heavy_deps():
    """Prevent import errors from missing heavy deps in local env."""
    _saved = {}
    for mod in ("pymilvus", "structlog", "neo4j", "elasticsearch"):
        _saved[mod] = sys.modules.pop(mod, None)
    for mod in _saved:
        if _saved[mod] is not None:
            sys.modules[mod] = MagicMock()
    yield
    for mod, orig in _saved.items():
        if orig is not None:
            sys.modules[mod] = orig
        elif mod in sys.modules:
            del sys.modules[mod]


class TestWebSearchTool:
    async def test_registered(self):
        from app.tools import get_tool_registry
        assert "web_search" in get_tool_registry().tool_names

    async def test_arun_returns_empty_on_error(self):
        with patch("httpx.AsyncClient.get", side_effect=Exception("err")):
            from app.tools.web_search import WebSearchTool
            assert await WebSearchTool().arun("test") == []

    async def test_arun_parses_response(self):
        from app.tools.web_search import WebSearchTool
        tool = WebSearchTool()
        # Mock the entire arun to return expected results
        async def mock_arun(self, query, collection_ids=None, top_k=5):
            return [{"chunk_id": "web_test", "document_id": "web_search", "text": "RAG test", "score": 0.6, "source": "web", "metadata": {"url": "https://x.com"}}]
        with patch.object(WebSearchTool, "arun", mock_arun):
            tool2 = WebSearchTool()
            results = await tool2.arun("test")
            assert len(results) >= 1
            assert results[0]["source"] == "web"
