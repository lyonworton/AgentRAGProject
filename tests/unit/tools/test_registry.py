import pytest
from app.tools.base import BaseTool
from app.tools import ToolRegistry


class _FakeTool(BaseTool):
    name = "fake"
    description = "A fake tool for testing"

    async def arun(self, query: str, collection_ids: list[str], top_k: int = 10) -> list[dict]:
        return [{"chunk_id": "1", "text": query, "score": 1.0, "source": "test"}]


@pytest.mark.asyncio
async def test_registry_register_and_get():
    registry = ToolRegistry()
    tool = _FakeTool()
    registry.register(tool)
    assert registry.get("fake") is tool


@pytest.mark.asyncio
async def test_registry_get_unknown_raises():
    registry = ToolRegistry()
    with pytest.raises(KeyError, match="Unknown tool: missing"):
        registry.get("missing")


@pytest.mark.asyncio
async def test_registry_tool_names_and_descriptions():
    registry = ToolRegistry()
    tool = _FakeTool()
    registry.register(tool)
    assert registry.tool_names == ["fake"]
    assert "fake: A fake tool for testing" in registry.tool_descriptions