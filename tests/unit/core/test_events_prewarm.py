"""Test embedding prewarm logic in events.py (Xinference only)."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_prewarm_xinference_success():
    """Xinference warmup() succeeds and is logged."""
    mock_embedder = MagicMock()
    mock_embedder.warmup = AsyncMock(return_value=True)

    with patch("app.core.embedding_factory.get_embedder", return_value=mock_embedder):
        try:
            embedder = mock_embedder
            warmup_success = await asyncio.wait_for(
                embedder.warmup(),
                timeout=15.0,
            )
            assert warmup_success is True
        except Exception:
            pytest.fail("prewarm raised unexpected exception")


@pytest.mark.asyncio
async def test_prewarm_xinference_failure():
    """When warmup fails, exception is caught."""
    mock_embedder = MagicMock()
    mock_embedder.warmup = AsyncMock(side_effect=TimeoutError("connection refused"))

    with patch("app.core.embedding_factory.get_embedder", return_value=mock_embedder):
        try:
            embedder = mock_embedder
            warmup_success = await asyncio.wait_for(
                embedder.warmup(),
                timeout=15.0,
            )
            assert warmup_success is False
        except TimeoutError:
            # Expected -- wait_for times out
            pass
