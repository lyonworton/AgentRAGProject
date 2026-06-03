import pytest
from unittest.mock import AsyncMock
from app.ingestion.keyword_path.es_writer import write_document_to_es


@pytest.mark.asyncio
async def test_write_document_to_es():
    mock_store = AsyncMock()
    mock_store.aindex_document.return_value = None

    await write_document_to_es(
        doc_id="doc_001",
        collection_id="col_123",
        title="测试文档",
        content="这是文档的完整内容，不会被分块。",
        metadata={"source_type": "local", "source_path": "/tmp/test.md"},
        search_store=mock_store,
    )

    mock_store.aindex_document.assert_called_once()
    call_args = mock_store.aindex_document.call_args
    assert call_args[0][0] == "col_123"
    assert call_args[0][1] == "doc_001"
    assert call_args[0][2] == "测试文档"
    assert call_args[0][3] == "这是文档的完整内容，不会被分块。"


@pytest.mark.asyncio
async def test_write_document_passes_metadata():
    mock_store = AsyncMock()
    mock_store.aindex_document.return_value = None

    metadata = {
        "source_type": "web",
        "source_path": "https://example.com/article",
        "mime_type": "text/html",
        "language": "zh",
        "page_number": None,
    }

    await write_document_to_es(
        doc_id="doc_002",
        collection_id="col_456",
        title="Web Article",
        content="Full content here.",
        metadata=metadata,
        search_store=mock_store,
    )

    passed_metadata = mock_store.aindex_document.call_args[0][4]
    assert passed_metadata["source_type"] == "web"
    assert passed_metadata["source_path"] == "https://example.com/article"