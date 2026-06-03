import pytest
from unittest.mock import AsyncMock
from app.ingestion.graph_path.neo4j_writer import write_graph_to_neo4j


@pytest.mark.asyncio
async def test_write_graph_to_neo4j():
    mock_store = AsyncMock()
    mock_store.acreate_graph.return_value = None

    entities = [
        {"id": "e1", "name": "阿里巴巴", "type": "organization", "aliases": ["阿里"]},
    ]
    relations = [
        {"from_entity": "e1", "to_entity": "e2", "type": "LOCATED_IN"},
    ]

    await write_graph_to_neo4j("doc_001", entities, relations, mock_store)

    mock_store.acreate_graph.assert_called_once_with(
        "doc_001", entities, relations
    )


@pytest.mark.asyncio
async def test_write_graph_empty_lists():
    mock_store = AsyncMock()
    await write_graph_to_neo4j("doc_001", [], [], mock_store)
    mock_store.acreate_graph.assert_called_once_with("doc_001", [], [])