"""Embedding factory — returns a configured embedding adapter singleton."""

from app.core.config import get_settings

_embedder = None


def get_embedder():
    """Return a local BGE-M3 embedding adapter (singleton)."""
    global _embedder
    if _embedder is not None:
        return _embedder

    from app.adapters.embedding.bge_m3 import BGEEmbedding

    settings = get_settings()
    model_path = settings.bge_embedding_model
    _embedder = BGEEmbedding(model_path=model_path)
    return _embedder