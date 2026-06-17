"""Verify that aembed_documents uses batch_size=256."""

import pytest
from unittest.mock import patch, MagicMock
from app.adapters.embedding.bge_m3 import BGEEmbedding


@pytest.mark.asyncio
async def test_batch_size_is_256():
    """Verify that aembed_documents uses batch_size=256."""
    embedder = BGEEmbedding(model_path="/nonexistent")
    mock_model = MagicMock()
    # Simulate numpy array output from model.encode()
    mock_array = MagicMock()
    mock_array.tolist.return_value = [[0.1] * 1024] * 5
    mock_model.encode.return_value = mock_array
    with patch.object(embedder, "_load_model_async", return_value=mock_model):
        texts = ["test " * 100] * 5
        await embedder.aembed_documents(texts)
        mock_model.encode.assert_called_once()
        call_kwargs = mock_model.encode.call_args.kwargs
        assert call_kwargs["batch_size"] == 256
