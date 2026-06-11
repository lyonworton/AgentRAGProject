"""Test executor_node reranking integration (Phase 5)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.agents.state import AgentState
from app.agents.executor import executor_node
from app.adapters.reranker.rrf import RRFReranker


def _make_state(sub_tasks=None, routes=None, collection_ids=None, query="test query"):
    state: AgentState = {
        "query": query, "conversation_history": [],
        "intent": "", "rewritten_query": "",
        "sub_tasks": sub_tasks or [],
        "routes": routes or {},
        "retrieved": [], "raw_milvus_hits": [], "raw_kg_results": [], "raw_keyword_hits": [],
        "reflection_notes": "", "missing_info": [], "quality_score": 0.0, "need_another_round": False,
        "draft_answer": "", "verified_claims": [], "supplement_queries": [], "need_supplement": False,
        "final_answer": "", "citations": [], "uncertainty_flags": [], "warnings": [], "bare_minimum_mode": False,
        "iteration": 0, "max_iterations": 5, "prev_score": None, "collection_ids": collection_ids or ["col1"],
        "routing_metrics": None,
    }
    return state


@pytest.mark.asyncio
async def test_executor_uses_reranker():
    """executor_node calls reranker and uses _rerank_score."""
    with patch("app.agents.executor.get_tool_registry") as mock_registry, \
         patch("app.adapters.reranker.factory.get_reranker", return_value=RRFReranker(k=60)):
        mock_tool = MagicMock()
        mock_tool.arun = AsyncMock(return_value=[
            {"chunk_id": "c1", "document_id": "d1", "text": "relevant text", "score": 0.9, "source": "milvus"},
            {"chunk_id": "c2", "document_id": "d2", "text": "less relevant", "score": 0.5, "source": "milvus"},
        ])
        mock_registry_instance = MagicMock()
        mock_registry_instance.get.return_value = mock_tool
        mock_registry.return_value = mock_registry_instance

        state = _make_state(
            query="test query",
            sub_tasks=[{"id": "t1", "description": "find", "intent": "fact", "depends_on": [], "status": "pending"}],
            routes={"t1": ["semantic_search"]},
        )
        result = await executor_node(state)
        assert len(result["retrieved"]) == 2
        # Documents should be sorted by _rerank_score (RRF), not raw score
        assert result["retrieved"][0]["score"] > 0
        assert result["retrieved"][1]["score"] > 0


@pytest.mark.asyncio
async def test_executor_empty_hits_no_rerank():
    """When all tools fail, empty all_hits, no reranker call, no crash."""
    with patch("app.agents.executor.get_tool_registry") as mock_registry:
        mock_tool = MagicMock()
        mock_tool.arun = AsyncMock(side_effect=Exception("Dead"))
        mock_registry_instance = MagicMock()
        mock_registry_instance.get.return_value = mock_tool
        mock_registry.return_value = mock_registry_instance

        state = _make_state(
            sub_tasks=[{"id": "t1", "description": "find", "intent": "fact", "depends_on": [], "status": "pending"}],
            routes={"t1": ["semantic_search"]},
        )
        result = await executor_node(state)
        assert result["retrieved"] == []


@pytest.mark.asyncio
async def test_executor_cross_source_rerank():
    """Multi-source results are fused by RRF, not raw score."""
    with patch("app.agents.executor.get_tool_registry") as mock_registry, \
         patch("app.adapters.reranker.factory.get_reranker", return_value=RRFReranker(k=60)):
        tool_semantic = MagicMock()
        tool_semantic.arun = AsyncMock(return_value=[
            {"chunk_id": "s1", "document_id": "d1", "text": "semantic", "score": 0.8, "source": "milvus"},
        ])
        tool_keyword = MagicMock()
        tool_keyword.arun = AsyncMock(return_value=[
            {"chunk_id": "k1", "document_id": "d2", "text": "keyword", "score": 50.0, "source": "keyword"},
        ])
        tool_kg = MagicMock()
        tool_kg.arun = AsyncMock(return_value=[
            {"chunk_id": "g1", "document_id": "d3", "text": "kg entity", "score": 0.5, "source": "kg"},
        ])

        mock_registry_instance = MagicMock()
        mock_registry_instance.get.side_effect = lambda name: {
            "semantic_search": tool_semantic,
            "keyword_search": tool_keyword,
            "kg_search": tool_kg,
        }[name]
        mock_registry.return_value = mock_registry_instance

        state = _make_state(
            sub_tasks=[{"id": "t1", "description": "find all", "intent": "reasoning", "depends_on": [], "status": "pending"}],
            routes={"t1": ["semantic_search", "keyword_search", "kg_search"]},
        )
        result = await executor_node(state)
        # All 3 results should be present, fused by RRF
        assert len(result["retrieved"]) == 3
        # Without RRF, the ES doc with score 50.0 would always be #1
        # With RRF, all rank-1 docs from each source get equal weight
        assert len(result["raw_milvus_hits"]) == 1
        assert len(result["raw_keyword_hits"]) == 1
        assert len(result["raw_kg_results"]) == 1