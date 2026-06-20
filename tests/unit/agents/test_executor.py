import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.agents.state import AgentState
from app.agents.executor import _resolve_groups
from app.adapters.reranker.rrf import RRFReranker


class TestResolveGroups:
    def test_no_dependencies_all_parallel(self):
        sub_tasks = [
            {"id": "t1", "depends_on": []},
            {"id": "t2", "depends_on": []},
        ]
        groups = _resolve_groups(sub_tasks)
        assert groups == [["t1", "t2"]]

    def test_linear_dependency_two_groups(self):
        sub_tasks = [
            {"id": "t1", "depends_on": []},
            {"id": "t2", "depends_on": ["t1"]},
        ]
        groups = _resolve_groups(sub_tasks)
        assert groups == [["t1"], ["t2"]]

    def test_diamond_dependency(self):
        sub_tasks = [
            {"id": "t1", "depends_on": []},
            {"id": "t2", "depends_on": ["t1"]},
            {"id": "t3", "depends_on": ["t1"]},
            {"id": "t4", "depends_on": ["t2", "t3"]},
        ]
        groups = _resolve_groups(sub_tasks)
        assert groups == [["t1"], ["t2", "t3"], ["t4"]]

    def test_circular_dependency_raises(self):
        sub_tasks = [
            {"id": "t1", "depends_on": ["t2"]},
            {"id": "t2", "depends_on": ["t1"]},
        ]
        with pytest.raises(ValueError, match="Circular dependency"):
            _resolve_groups(sub_tasks)

    def test_unknown_dependency_raises(self):
        sub_tasks = [
            {"id": "t1", "depends_on": ["nonexistent"]},
        ]
        with pytest.raises(ValueError, match="depends on unknown task"):
            _resolve_groups(sub_tasks)

    def test_empty_list(self):
        groups = _resolve_groups([])
        assert groups == []


# ── Executor integration tests ──────────────────────────────────────────

from app.agents.executor import executor_node


def _make_state(sub_tasks=None, routes=None, collection_ids=None):
    state: AgentState = {
        "query": "test", "conversation_history": [],
        "intent": "", "rewritten_query": "",
        "sub_tasks": sub_tasks or [],
        "routes": routes or {},
        "retrieved": [], "raw_milvus_hits": [], "raw_kg_results": [], "raw_keyword_hits": [],
        "reflection_notes": "", "missing_info": [], "quality_score": 0.0, "need_another_round": False,
        "draft_answer": "", "verified_claims": [], "supplement_queries": [], "need_supplement": False,
        "final_answer": "", "citations": [], "uncertainty_flags": [], "warnings": [], "bare_minimum_mode": False,
        "iteration": 0, "max_iterations": 2, "prev_score": None, "collection_ids": collection_ids or ["col1"],
        "routing_metrics": None,
    }
    return state


@pytest.mark.asyncio
async def test_executor_single_tool_success():
    with patch("app.agents.executor.get_tool_registry") as mock_registry, \
         patch("app.adapters.reranker.factory.get_reranker", return_value=RRFReranker(k=60)):
        mock_tool = MagicMock()
        mock_tool.arun = AsyncMock(return_value=[
            {"chunk_id": "c1", "document_id": "d1", "text": "hello", "score": 0.9, "source": "milvus"},
        ])
        mock_registry_instance = MagicMock()
        mock_registry_instance.get.return_value = mock_tool
        mock_registry.return_value = mock_registry_instance

        state = _make_state(
            sub_tasks=[{"id": "t1", "description": "find", "intent": "fact", "depends_on": [], "status": "pending"}],
            routes={"t1": ["semantic_search"]},
        )
        result = await executor_node(state)
        assert len(result["retrieved"]) == 1
        assert result["retrieved"][0]["chunk_id"] == "c1"
        assert len(result["raw_milvus_hits"]) == 1
        assert len(result["raw_kg_results"]) == 0
        assert len(result["raw_keyword_hits"]) == 0


@pytest.mark.asyncio
async def test_executor_tool_failure_isolated():
    with patch("app.agents.executor.get_tool_registry") as mock_registry, \
         patch("app.adapters.reranker.factory.get_reranker", return_value=RRFReranker(k=60)):
        mock_tool_success = MagicMock()
        mock_tool_success.arun = AsyncMock(return_value=[
            {"chunk_id": "c1", "document_id": "d1", "text": "ok", "score": 0.9, "source": "milvus"},
        ])
        mock_tool_fail = MagicMock()
        mock_tool_fail.arun = AsyncMock(side_effect=Exception("Tool error"))

        mock_registry_instance = MagicMock()
        mock_registry_instance.get.side_effect = lambda name: {
            "semantic_search": mock_tool_success,
            "kg_search": mock_tool_fail,
        }[name]
        mock_registry.return_value = mock_registry_instance

        state = _make_state(
            sub_tasks=[{"id": "t1", "description": "find", "intent": "reasoning", "depends_on": [], "status": "pending"}],
            routes={"t1": ["semantic_search", "kg_search"]},
        )
        result = await executor_node(state)
        assert len(result["retrieved"]) == 1
        assert len(result["warnings"]) == 1
        assert "kg_search" in result["warnings"][0]


@pytest.mark.asyncio
async def test_executor_deduplicates_by_chunk_id():
    with patch("app.agents.executor.get_tool_registry") as mock_registry, \
         patch("app.adapters.reranker.factory.get_reranker", return_value=RRFReranker(k=60)):
        mock_tool = MagicMock()
        mock_tool.arun = AsyncMock(return_value=[
            {"chunk_id": "c1", "document_id": "d1", "text": "hello", "score": 0.9, "source": "milvus"},
            {"chunk_id": "c1", "document_id": "d1", "text": "hello", "score": 0.7, "source": "keyword"},
        ])
        mock_registry_instance = MagicMock()
        mock_registry_instance.get.return_value = mock_tool
        mock_registry.return_value = mock_registry_instance

        state = _make_state(
            sub_tasks=[{"id": "t1", "description": "find", "intent": "fact", "depends_on": [], "status": "pending"}],
            routes={"t1": ["semantic_search", "keyword_search"]},
        )
        result = await executor_node(state)
        assert len(result["retrieved"]) == 1
        assert result["retrieved"][0]["score"] > 0  # Phase 5: _rerank_score from RRF


@pytest.mark.asyncio
async def test_executor_empty_subtasks_returns_empty():
    state = _make_state(sub_tasks=[], routes={})
    result = await executor_node(state)
    assert result["retrieved"] == []
    assert result["warnings"] == []


@pytest.mark.asyncio
async def test_executor_subtask_status_updated():
    with patch("app.agents.executor.get_tool_registry") as mock_registry, \
         patch("app.adapters.reranker.factory.get_reranker", return_value=RRFReranker(k=60)):
        mock_tool = MagicMock()
        mock_tool.arun = AsyncMock(return_value=[
            {"chunk_id": "c1", "document_id": "d1", "text": "ok", "score": 0.9, "source": "milvus"},
        ])
        mock_registry_instance = MagicMock()
        mock_registry_instance.get.return_value = mock_tool
        mock_registry.return_value = mock_registry_instance

        state = _make_state(
            sub_tasks=[{"id": "t1", "description": "find", "intent": "fact", "depends_on": [], "status": "pending"}],
            routes={"t1": ["semantic_search"]},
        )
        result = await executor_node(state)
        assert result["sub_tasks"][0]["status"] == "done"


@pytest.mark.asyncio
async def test_executor_subtask_all_tools_fail():
    with patch("app.agents.executor.get_tool_registry") as mock_registry:
        mock_tool = MagicMock()
        mock_tool.arun = AsyncMock(side_effect=Exception("All dead"))
        mock_registry_instance = MagicMock()
        mock_registry_instance.get.return_value = mock_tool
        mock_registry.return_value = mock_registry_instance

        state = _make_state(
            sub_tasks=[{"id": "t1", "description": "find", "intent": "fact", "depends_on": [], "status": "pending"}],
            routes={"t1": ["semantic_search"]},
        )
        result = await executor_node(state)
        assert result["sub_tasks"][0]["status"] == "failed"
        assert result["retrieved"] == []


@pytest.mark.asyncio
async def test_executor_computes_routing_metrics():
    """executor_node populates routing_metrics with tool counts and source diversity."""
    with patch("app.agents.executor.get_tool_registry") as mock_registry, \
         patch("app.adapters.reranker.factory.get_reranker", return_value=RRFReranker(k=60)):
        tool_semantic = MagicMock()
        tool_semantic.arun = AsyncMock(return_value=[
            {"chunk_id": "c1", "document_id": "d1", "text": "milvus result", "score": 0.8, "source": "milvus"},
        ])
        tool_keyword = MagicMock()
        tool_keyword.arun = AsyncMock(return_value=[
            {"chunk_id": "c2", "document_id": "d2", "text": "es result", "score": 50.0, "source": "keyword"},
        ])

        mock_registry_instance = MagicMock()
        mock_registry_instance.get.side_effect = lambda name: {
            "semantic_search": tool_semantic,
            "keyword_search": tool_keyword,
        }[name]
        mock_registry.return_value = mock_registry_instance

        state = _make_state(
            sub_tasks=[{"id": "t1", "description": "find", "intent": "fact", "depends_on": [], "status": "pending"}],
            routes={"t1": ["semantic_search", "keyword_search"]},
        )
        result = await executor_node(state)

        metrics = result["routing_metrics"]
        assert metrics is not None
        assert metrics["tools_selected"] == {"semantic_search": 1, "keyword_search": 1}
        assert metrics["results_per_tool"]["semantic_search"] == 1
        assert metrics["results_per_tool"]["keyword_search"] == 1
        assert metrics["source_diversity"] == 1.0  # both sources present
        assert "milvus" in metrics["sources_in_final"]
        assert "keyword" in metrics["sources_in_final"]