import pytest
from unittest.mock import AsyncMock
from app.ingestion.graph_path.relation_extractor import extract_relations, RELATION_SCHEMA


def test_relation_schema_has_required_fields():
    schema = RELATION_SCHEMA
    assert "entities" in schema["properties"]
    assert "relations" in schema["properties"]
    entity_props = schema["properties"]["entities"]["items"]["properties"]
    assert "id" in entity_props
    assert "name" in entity_props
    assert "type" in entity_props
    assert "aliases" in entity_props
    rel_props = schema["properties"]["relations"]["items"]["properties"]
    assert "from_entity" in rel_props
    assert "to_entity" in rel_props
    assert "type" in rel_props


@pytest.mark.asyncio
async def test_extract_relations_mock_llm():
    mock_llm = AsyncMock()
    mock_llm.agenerate_structured.return_value = {
        "entities": [
            {"id": "e1", "name": "阿里巴巴", "type": "organization", "aliases": ["阿里"]},
            {"id": "e2", "name": "杭州", "type": "location", "aliases": []},
        ],
        "relations": [
            {"from_entity": "e1", "to_entity": "e2", "type": "LOCATED_IN"},
        ],
    }

    entities = [
        {"name": "阿里巴巴", "score": 0.8, "type": "organization"},
        {"name": "杭州", "score": 0.6, "type": "location"},
    ]
    text = "阿里巴巴总部位于杭州。"

    result = await extract_relations(text, entities, mock_llm)

    assert "entities" in result
    assert "relations" in result
    assert len(result["entities"]) == 2
    assert len(result["relations"]) == 1
    mock_llm.agenerate_structured.assert_called_once()


@pytest.mark.asyncio
async def test_extract_relations_empty_entities():
    mock_llm = AsyncMock()
    mock_llm.agenerate_structured.return_value = {"entities": [], "relations": []}

    result = await extract_relations("some text", [], mock_llm)
    assert result["entities"] == []
    assert result["relations"] == []