"""Test embedding_factory always returns XinferenceEmbedding."""

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
    for key in ["XINFERENCE_ENDPOINT", "XINFERENCE_EMBEDDING_MODEL"]:
        if key in os.environ:
            del os.environ[key]


def test_always_returns_xinference_adapter():
    """Always returns XinferenceEmbedding (no local fallback)."""
    embedder = get_embedder()
    assert type(embedder).__name__ == "XinferenceEmbedding"
    assert embedder.model == "bge-m3"
