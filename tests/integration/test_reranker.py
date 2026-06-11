"""Integration tests: pluggable reranker — factory, RRF, TwoStageReranker."""

import pytest


@pytest.mark.integration
class TestReranker:
    def test_factory_default_is_valid(self):
        """Default provider returns a valid BaseReranker (bge→TwoStageReranker)."""
        from app.adapters.reranker.factory import get_reranker
        from app.adapters.reranker.base import BaseReranker

        get_reranker.cache_clear()
        reranker = get_reranker()
        assert isinstance(reranker, BaseReranker)

    def test_factory_unknown_provider_falls_back(self, monkeypatch):
        """Unknown provider returns RRF."""
        from app.adapters.reranker.factory import get_reranker
        from app.adapters.reranker.rrf import RRFReranker

        get_reranker.cache_clear()
        monkeypatch.setenv("RERANKER_PROVIDER", "nonexistent")
        from app.core.config import get_settings
        get_settings.cache_clear()

        import app.adapters.reranker.factory as factory_mod
        factory_mod.get_reranker.cache_clear()

        reranker = factory_mod.get_reranker()
        assert isinstance(reranker, RRFReranker)

    async def test_rrf_single_source_preserves_order(self):
        """Within one source, RRF keeps score-based ranking."""
        from app.adapters.reranker.rrf import RRFReranker

        rrf = RRFReranker(k=60)
        docs = [
            {"chunk_id": "a", "text": "first", "score": 0.9, "source": "test", "_tool": "semantic_search"},
            {"chunk_id": "b", "text": "second", "score": 0.5, "source": "test", "_tool": "semantic_search"},
            {"chunk_id": "c", "text": "third", "score": 0.8, "source": "test", "_tool": "semantic_search"},
        ]
        result = await rrf.rerank("query", docs, top_k=10)
        ids = [d["chunk_id"] for d in result]
        assert ids == ["a", "c", "b"]  # 0.9 > 0.8 > 0.5

    async def test_two_stage_both_stages_called(self):
        """TwoStageReranker calls stage1 then stage2."""
        from app.adapters.reranker.base import TwoStageReranker
        from app.adapters.reranker.rrf import RRFReranker

        stage1 = RRFReranker(k=60)
        stage2 = RRFReranker(k=30)  # same algorithm, different k for testing
        ts = TwoStageReranker(stage1, stage2, top_k=3)

        docs = [
            {"chunk_id": f"d{i}", "text": f"text-{i}", "score": float(10 - i),
             "source": "test", "_tool": "semantic_search"}
            for i in range(10)
        ]
        result = await ts.rerank("query", docs, top_k=5)
        assert len(result) <= 5
        for d in result:
            assert "_rerank_score" in d