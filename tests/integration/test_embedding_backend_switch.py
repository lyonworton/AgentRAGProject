"""End-to-end test: verify embedding backend (Xinference GPU) works."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.core.embedding_factory import get_embedder, _reset_singleton


@pytest.fixture(autouse=True)
def clean_singleton():
    _reset_singleton()
    yield
    _reset_singleton()


@pytest.mark.asyncio
async def test_xinference_backend_embeds_documents():
    """Xinference backend produces valid embeddings via AsyncOpenAI."""
    embedder = get_embedder()
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
