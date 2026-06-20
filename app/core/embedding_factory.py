"""Embedding factory — returns a configured embedding adapter singleton."""

from app.core.config import get_settings

_embedder = None


def _reset_singleton():
    """Reset the embedding singleton (for testing)."""
    global _embedder
    _embedder = None


def get_embedder():
    """Return an embedding adapter based on EMBEDDING_BACKEND config."""
    global _embedder
    if _embedder is not None:
        return _embedder

    s = get_settings()

    from app.adapters.embedding.xinference import XinferenceEmbedding
    _embedder = XinferenceEmbedding(
        endpoint=s.xinference_endpoint,
        model=s.xinference_embedding_model,
    )

    return _embedder