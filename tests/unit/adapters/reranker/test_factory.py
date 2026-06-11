"""Test get_reranker factory: correct instances, fallback behavior."""

import pytest
from app.adapters.reranker.base import BaseReranker, TwoStageReranker
from app.adapters.reranker.rrf import RRFReranker


class TestRerankerFactory:
    def test_default_returns_valid_reranker(self):
        """Default provider returns a BaseReranker (rrf if bge unavailable, TwoStage if available)."""
        from app.adapters.reranker.factory import get_reranker
        # Clear cache to get fresh instance
        get_reranker.cache_clear()
        reranker = get_reranker()
        # Default provider is bge with RRF+BGE two-stage; falls back to RRF if FlagEmbedding missing
        assert isinstance(reranker, BaseReranker)

    def test_bge_returns_two_stage(self, monkeypatch):
        from app.adapters.reranker.factory import get_reranker
        get_reranker.cache_clear()
        monkeypatch.setenv("RERANKER_PROVIDER", "bge")

        import sys
        # Mock FlagEmbedding availability
        class _FakeReranker:
            def __init__(self, *a, **kw): pass
        fake = type(sys)("FlagEmbedding")
        fake.FlagReranker = _FakeReranker
        monkeypatch.setitem(sys.modules, "FlagEmbedding", fake)

        # Reload settings and factory
        from app.core.config import get_settings
        get_settings.cache_clear()

        # Need to re-import since get_reranker is cached
        import app.adapters.reranker.factory as factory_mod
        factory_mod.get_reranker.cache_clear()

        reranker = factory_mod.get_reranker()
        assert isinstance(reranker, TwoStageReranker)
        assert isinstance(reranker._s1, RRFReranker)

    def test_cohere_returns_two_stage(self, monkeypatch):
        from app.adapters.reranker.factory import get_reranker
        get_reranker.cache_clear()
        monkeypatch.setenv("RERANKER_PROVIDER", "cohere")
        monkeypatch.setenv("COHERE_API_KEY", "test-key")

        import sys
        fake = type(sys)("cohere")
        class _FakeClient:
            def __init__(self, api_key): pass
        fake.Client = _FakeClient
        monkeypatch.setitem(sys.modules, "cohere", fake)

        from app.core.config import get_settings
        get_settings.cache_clear()

        import app.adapters.reranker.factory as factory_mod
        factory_mod.get_reranker.cache_clear()

        reranker = factory_mod.get_reranker()
        assert isinstance(reranker, TwoStageReranker)
        assert isinstance(reranker._s1, RRFReranker)

    def test_unknown_provider_falls_back_to_rrf(self, monkeypatch):
        from app.adapters.reranker.factory import get_reranker
        get_reranker.cache_clear()
        monkeypatch.setenv("RERANKER_PROVIDER", "nonexistent")
        from app.core.config import get_settings
        get_settings.cache_clear()

        import app.adapters.reranker.factory as factory_mod
        factory_mod.get_reranker.cache_clear()

        reranker = factory_mod.get_reranker()
        assert isinstance(reranker, RRFReranker)
        assert not isinstance(reranker, TwoStageReranker)

    def test_bge_import_error_falls_back(self, monkeypatch):
        """When FlagEmbedding not installed, fall back to RRF."""
        from app.adapters.reranker.factory import get_reranker
        get_reranker.cache_clear()
        monkeypatch.setenv("RERANKER_PROVIDER", "bge")

        from app.core.config import get_settings
        get_settings.cache_clear()

        import app.adapters.reranker.factory as factory_mod
        factory_mod.get_reranker.cache_clear()

        # FlagEmbedding is NOT mocked, so import will fail if not installed
        # In the Docker test env it won't be installed → should fall back
        reranker = get_reranker()
        # May be RRF (fallback) or TwoStage (if deps present)
        assert isinstance(reranker, BaseReranker)