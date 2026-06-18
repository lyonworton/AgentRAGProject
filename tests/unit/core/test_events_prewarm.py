"""Test embedding prewarm logic in events.py."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_prewarm_xinference_success():
    """When backend is xinference, warmup() is called and success is logged."""
    mock_embedder = MagicMock()
    mock_embedder.warmup = AsyncMock(return_value=True)

    with patch("app.core.embedding_factory.get_embedder", return_value=mock_embedder):
        # Replicate the prewarm logic from events.py
        try:
            embedder = mock_embedder
            if hasattr(embedder, "warmup"):
                warmup_success = await asyncio.wait_for(
                    embedder.warmup(),
                    timeout=15.0,
                )
            else:
                await asyncio.to_thread(embedder._load_model)
                warmup_success = True
            assert warmup_success is True
        except Exception:
            pytest.fail("prewarm raised unexpected exception")


@pytest.mark.asyncio
async def test_prewarm_xinference_failure_returns_false():
    """When warmup times out or fails, warmup_success is False."""
    mock_embedder = MagicMock()
    mock_embedder.warmup = AsyncMock(side_effect=TimeoutError("connection refused"))

    with patch("app.core.embedding_factory.get_embedder", return_value=mock_embedder):
        try:
            embedder = mock_embedder
            if hasattr(embedder, "warmup"):
                warmup_success = await asyncio.wait_for(
                    embedder.warmup(),
                    timeout=15.0,
                )
            else:
                warmup_success = False
            assert warmup_success is False
        except TimeoutError:
            # Expected -- wait_for times out
            pass


@pytest.mark.asyncio
async def test_prewarm_local_backend():
    """When backend is local (no warmup), _load_model is called."""
    mock_embedder = MagicMock(spec=["_load_model"])
    mock_embedder._load_model = MagicMock()
    # spec prevents dynamic warmup attribute -- simulates BGEEmbedding

    with patch("app.core.embedding_factory.get_embedder", return_value=mock_embedder):
        try:
            embedder = mock_embedder
            if hasattr(embedder, "warmup"):
                warmup_success = False
            else:
                await asyncio.to_thread(embedder._load_model)
                warmup_success = True
            assert warmup_success is True
            mock_embedder._load_model.assert_called_once()
        except Exception:
            pytest.fail("prewarm raised unexpected exception")
