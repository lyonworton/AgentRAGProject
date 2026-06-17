import pytest
from unittest.mock import MagicMock, AsyncMock, patch


@pytest.mark.asyncio
async def test_write_chunks_no_flush():
    """write_chunks_to_milvus should NOT flush the collection by default."""
    from app.ingestion.semantic_path.milvus_writer import write_chunks_to_milvus

    mock_store = AsyncMock()
    mock_store.insert = AsyncMock()
    mock_store.insert.return_value = None

    with patch("app.ingestion.semantic_path.milvus_writer.MilvusStore", return_value=mock_store):
        chunks = [{"text": "chunk1", "metadata": {}}, {"text": "chunk2", "metadata": {}}]
        embeddings = [[0.1, 0.2], [0.3, 0.4]]
        count = await write_chunks_to_milvus("col_test", "doc_1", chunks, embeddings)
        assert count == 2
        mock_store.insert.assert_called_once()
        # Verify flush=False was passed
        call_kwargs = mock_store.insert.call_args.kwargs
        assert call_kwargs.get("flush") is False


@pytest.mark.asyncio
async def test_flush_collection():
    """flush_collection should call col.flush() on the collection."""
    from app.adapters.vector_store.milvus import MilvusStore

    with patch.object(MilvusStore, "__init__", return_value=None), \
         patch("app.adapters.vector_store.milvus.Collection") as MockCol:
        mock_instance = MagicMock()
        MockCol.return_value = mock_instance
        store = MilvusStore()
        await store.flush_collection("col_test")
        mock_instance.flush.assert_called_once()
