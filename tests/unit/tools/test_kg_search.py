import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.tools.kg_search import KGSearchTool


@pytest.mark.asyncio
async def test_kg_search_entities_and_relations():
    tool = KGSearchTool()
    assert tool.name == "kg_search"
    assert "Neo4j" in tool.description

    with patch("app.tools.kg_search.Neo4jKGStore") as mock_kg:
        mock_instance = MagicMock()
        mock_instance.asearch_entities = AsyncMock(return_value=[
            {"id": "ent1", "name": "Zhang San", "type": "PERSON"},
            {"id": "ent2", "name": "Tencent", "type": "ORG"},
        ])
        mock_instance.aquery_relations = AsyncMock(return_value=[
            {"from": "ent1", "type": "WORKS_AT", "to": "ent2"},
        ])
        mock_kg.return_value = mock_instance

        results = await tool.arun("Zhang San", [])

        assert len(results) >= 4  # 2 entities + 2 relations (both entities expand)
        entity_result = [r for r in results if "Entity:" in r["text"]]
        assert len(entity_result) == 2
        assert entity_result[0]["source"] == "kg"
        assert entity_result[0]["score"] == 0.5
        rel_result = [r for r in results if "WORKS_AT" in r["text"]]
        assert len(rel_result) == 2
        assert "WORKS_AT" in rel_result[0]["text"]


@pytest.mark.asyncio
async def test_kg_search_empty_results():
    tool = KGSearchTool()
    with patch("app.tools.kg_search.Neo4jKGStore") as mock_kg:
        mock_instance = MagicMock()
        mock_instance.asearch_entities = AsyncMock(return_value=[])
        mock_kg.return_value = mock_instance

        results = await tool.arun("nonexistent", [])
        assert results == []


@pytest.mark.asyncio
async def test_kg_search_limits_relation_expansion():
    """Only top 5 entities get relations expanded."""
    tool = KGSearchTool()
    with patch("app.tools.kg_search.Neo4jKGStore") as mock_kg:
        mock_instance = MagicMock()
        mock_instance.asearch_entities = AsyncMock(return_value=[
            {"id": f"ent{i}", "name": f"Entity{i}", "type": "THING"}
            for i in range(10)
        ])
        mock_instance.aquery_relations = AsyncMock(return_value=[])
        mock_kg.return_value = mock_instance

        results = await tool.arun("test", [])
        assert len(results) == 10
        assert mock_instance.aquery_relations.call_count == 5