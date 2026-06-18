"""End-to-end test: verify embedding backend switch works."""

import pytest
import os
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture(autouse=True)
def clean_env():
    """Clean up env vars after each test."""
    yield
    for key in ["EMBEDDING_BACKEND", "XINFERENCE_ENDPOINT", "XINFERENCE_EMBEDDING_MODEL"]:
        if key in os.environ:
            del os.environ[key]


@pytest.mark.asyncio
async def test_local_backend_embeds_documents():
    """Local backend produces valid embeddings."""
    if "EMBEDDING_BACKEND" in os.environ:
        del os.environ["EMBEDDING_BACKEND"]

    from app.core import embedding_factory
    embedding_factory._reset_singleton()

    embedder = embedding_factory.get_embedder()
    assert type(embedder).__name__ == "BGEEmbedding"

    # Mock the model encode to avoid loading BGE-M3
    mock_model = MagicMock()
    mock_array = MagicMock()
    mock_array.tolist.return_value = [[0.1] * 1024, [0.2] * 1024]
    mock_model.encode.return_value = mock_array

    with patch.object(embedder, "_load_model_async", return_value=mock_model):
        texts = ["doc one", "doc two"]
        result = await embedder.aembed_documents(texts)
        assert len(result) == 2
        assert len(result[0]) == 1024


@pytest.mark.asyncio
async def test_xinference_backend_embeds_documents():
    """Xinference backend produces valid embeddings via AsyncOpenAI."""
    os.environ["EMBEDDING_BACKEND"] = "xinference"

    from app.core.config import get_settings
    get_settings.cache_clear()

    from app.core import embedding_factory
    embedding_factory._reset_singleton()

    embedder = embedding_factory.get_embedder()
    assert type(embedder).__name__ == "XinferenceEmbedding"

    mock_resp = MagicMock()
    mock_resp.data = [
        MagicMock(embedding=[0.1] * 1024),
        MagicMock(embedding=[0.2] * 1024),
    ]
    embedder.client.embeddings.create = AsyncMock(return_value=mock_resp)

    texts = ["doc one", "doc two"]
    result = await embedder.aembed_documents(texts)
    assert len(result) == 2
    assert len(result[0]) == 1024
