"""Test XinferenceEmbedding adapter."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from openai import APITimeoutError
from app.adapters.embedding.xinference import XinferenceEmbedding


@pytest.mark.asyncio
async def test_aembed_query_calls_xinference():
    """Verify aembed_query sends a single text and returns embedding list."""
    adapter = XinferenceEmbedding(
        endpoint="http://xinference:9997",
        model="bge-m3",
    )

    mock_resp = MagicMock()
    mock_resp.data = [MagicMock(embedding=[0.1] * 1024)]
    adapter.client.embeddings.create = AsyncMock(return_value=mock_resp)

    result = await adapter.aembed_query("hello world")

    assert len(result) == 1024
    adapter.client.embeddings.create.assert_called_once()
    call_args = adapter.client.embeddings.create.call_args
    assert call_args.kwargs["model"] == "bge-m3"
    assert call_args.kwargs["input"] == ["hello world"]


@pytest.mark.asyncio
async def test_aembed_documents_returns_batch_embeddings():
    """Verify aembed_documents sends all texts and returns one embedding per text."""
    adapter = XinferenceEmbedding(
        endpoint="http://xinference:9997",
        model="bge-m3",
    )

    mock_resp = MagicMock()
    mock_resp.data = [
        MagicMock(embedding=[0.1] * 1024),
        MagicMock(embedding=[0.2] * 1024),
        MagicMock(embedding=[0.3] * 1024),
    ]
    adapter.client.embeddings.create = AsyncMock(return_value=mock_resp)

    texts = ["doc 1", "doc 2", "doc 3"]
    result = await adapter.aembed_documents(texts)

    assert len(result) == 3
    assert len(result[0]) == 1024
    adapter.client.embeddings.create.assert_called_once()
    call_args = adapter.client.embeddings.create.call_args
    assert call_args.kwargs["model"] == "bge-m3"
    assert call_args.kwargs["input"] == texts


@pytest.mark.asyncio
async def test_warmup_success():
    """warmup returns True when Xinference responds."""
    adapter = XinferenceEmbedding(
        endpoint="http://xinference:9997",
        model="bge-m3",
    )

    mock_resp = MagicMock()
    mock_resp.data = [MagicMock(embedding=[0.0] * 1024)]
    adapter.client.embeddings.create = AsyncMock(return_value=mock_resp)

    result = await adapter.warmup()
    assert result is True


@pytest.mark.asyncio
async def test_warmup_timeout_falls_back():
    """warmup returns False on connection error."""
    adapter = XinferenceEmbedding(
        endpoint="http://nonexistent:9997",
        model="bge-m3",
    )

    # AsyncOpenAI constructor still works; only the API call fails
    mock_client = MagicMock()
    mock_client.embeddings.create = AsyncMock(side_effect=APITimeoutError("connection refused"))
    adapter.client = mock_client

    result = await adapter.warmup()
    assert result is False
