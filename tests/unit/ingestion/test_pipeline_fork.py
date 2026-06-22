import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.ingestion.pipeline import (
    run_semantic_path, run_graph_path, run_keyword_path,
    _compute_path_status, batch_flush_milvus,
)


@pytest.mark.asyncio
@patch("app.ingestion.pipeline.embed_chunks")
@patch("app.ingestion.pipeline.get_settings")
@patch("app.ingestion.pipeline.chunk_text")
async def test_run_semantic_path(mock_chunk, mock_settings, mock_embed):
    mock_settings.return_value.preprocessor_enabled = False
    mock_settings.return_value.embedding_dim = 1536
    mock_chunk.return_value = [{"text": "chunk1", "metadata": {}}]
    mock_embed.return_value = [[0.1, 0.2]]

    doc = MagicMock()
    doc.content = "test content"
    doc.id = "doc_001"
    doc.source_path = "/tmp/test.txt"

    result = await run_semantic_path(doc, "col_123", 1536)
    assert result["count"] == 1
    assert result["doc_id"] == "doc_001"
    assert len(result["chunks"]) == 1
    assert len(result["embeddings"]) == 1


@pytest.mark.asyncio
@patch("app.adapters.llm.openai.OpenAILLM", return_value=MagicMock())
@patch("app.ingestion.graph_path.neo4j_writer.write_graph_to_neo4j")
@patch("app.core.di.get_kg_store")
@patch("app.ingestion.graph_path.relation_extractor.extract_relations")
@patch("app.ingestion.graph_path.entity_extractor.extract_candidate_entities")
async def test_run_graph_path(mock_extract_ent, mock_extract_rel, mock_kg, mock_write, mock_llm):
    mock_kg.return_value = AsyncMock()
    mock_extract_ent.return_value = [{"name": "Test", "score": 0.9, "type": "concept"}]
    mock_extract_rel.return_value = {
        "entities": [{"id": "e1", "name": "Test", "type": "concept", "aliases": []}],
        "relations": [],
    }
    mock_write.return_value = None

    doc = MagicMock()
    doc.content = "test content"
    doc.id = "doc_001"

    await run_graph_path(doc)
    mock_extract_ent.assert_called_once()
    mock_extract_rel.assert_called_once()
    mock_write.assert_called_once()


@pytest.mark.asyncio
@patch("app.ingestion.keyword_path.es_writer.write_document_to_es")
@patch("app.core.di.get_search_store")
async def test_run_keyword_path(mock_search, mock_write):
    mock_search.return_value = AsyncMock()
    mock_write.return_value = None

    doc = MagicMock()
    doc.id = "doc_001"
    doc.title = "Test Doc"
    doc.content = "Full content"
    doc.metadata_ = {"source_type": "local"}

    await run_keyword_path(doc, "col_123")
    mock_write.assert_called_once()


def test_compute_path_status_all_ok():
    results = [1, None, None]
    status = _compute_path_status(results)
    assert status == {"milvus": "ok", "neo4j": "ok", "es": "ok"}


def test_compute_path_status_neo4j_failed():
    results = [1, Exception("Neo4j down"), None]
    status = _compute_path_status(results)
    assert status == {"milvus": "ok", "neo4j": "error", "es": "ok"}


def test_compute_path_status_milvus_failed():
    results = [Exception("Milvus down"), None, None]
    status = _compute_path_status(results)
    assert status == {"milvus": "error", "neo4j": "ok", "es": "ok"}


def test_compute_path_status_all_failed():
    results = [Exception("a"), Exception("b"), Exception("c")]
    status = _compute_path_status(results)
    assert status == {"milvus": "error", "neo4j": "error", "es": "error"}
@pytest.mark.asyncio
@patch("app.ingestion.pipeline.MilvusStore")
async def test_batch_flush_milvus_writes_all_chunks(mock_store_cls):
    """batch_flush_milvus should insert all chunks across docs in batches of 1000."""
    mock_store = MagicMock()
    mock_store.insert = AsyncMock()
    mock_store_cls.return_value = mock_store

    batch_data = [
        {"doc_id": "d1", "chunks": [{"text": f"chunk{i}", "metadata": {}} for i in range(5)],
         "embeddings": [[0.1] * 1024] * 5, "count": 5},
        {"doc_id": "d2", "chunks": [{"text": f"chunk{i}", "metadata": {}} for i in range(5)],
         "embeddings": [[0.2] * 1024] * 5, "count": 5},
    ]

    count = await batch_flush_milvus("col_test", batch_data)
    assert count == 10
    mock_store.insert.assert_called_once()
    call_kwargs = mock_store.insert.call_args.kwargs
    assert call_kwargs["flush"] is True


@pytest.mark.asyncio
async def test_run_ingest_pipeline_accepts_commit_every():
    """run_ingest_pipeline should accept commit_every parameter."""
    from app.ingestion.pipeline import run_ingest_pipeline
    params = run_ingest_pipeline.__code__.co_varnames
    assert "commit_every" in params
