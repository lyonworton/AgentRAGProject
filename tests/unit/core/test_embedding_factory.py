"""Test embedding_factory routes to correct backend."""

import os
import pytest
from app.core.embedding_factory import get_embedder, _reset_singleton


@pytest.fixture(autouse=True)
def clean_singleton():
    """Reset singleton before and after each test."""
    _reset_singleton()
    yield
    _reset_singleton()


@pytest.fixture(autouse=True)
def clean_env():
    """Clean up env vars after each test."""
    yield
    if "EMBEDDING_BACKEND" in os.environ:
        del os.environ["EMBEDDING_BACKEND"]


def test_default_returns_local_bge():
    """Without EMBEDDING_BACKEND set, should return BGEEmbedding (local)."""
    embedder = get_embedder()
    assert type(embedder).__name__ == "BGEEmbedding"


def test_xinference_backend_returns_xinference_adapter():
    """With EMBEDDING_BACKEND=xinference, should return XinferenceEmbedding."""
    os.environ["EMBEDDING_BACKEND"] = "xinference"
    # Need fresh settings - create a new Settings instance
    from app.core.config import get_settings
    get_settings.cache_clear()

    _reset_singleton()
    embedder = get_embedder()
    assert type(embedder).__name__ == "XinferenceEmbedding"
    assert embedder.model == "bge-m3"

    # Restore for other tests
    get_settings.cache_clear()
    _reset_singleton()
