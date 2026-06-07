import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.agents.state import AgentState
from app.agents.router import route_node, FALLBACK_RULES


def _make_state(sub_tasks=None):
    state: AgentState = {
        "query": "test", "conversation_history": [],
        "intent": "", "rewritten_query": "",
        "sub_tasks": sub_tasks or [],
        "routes": {}, "retrieved": [], "raw_milvus_hits": [], "raw_kg_results": [], "raw_keyword_hits": [],
        "reflection_notes": "", "missing_info": [], "quality_score": 0.0, "need_another_round": False,
        "draft_answer": "", "verified_claims": [], "supplement_queries": [], "need_supplement": False,
        "final_answer": "", "citations": [], "uncertainty_flags": [], "warnings": [], "bare_minimum_mode": False,
        "iteration": 0, "max_iterations": 5, "prev_score": None, "collection_ids": [],
    }
    return state


@pytest.mark.asyncio
async def test_router_llm_routing():
    with patch("app.agents.router.get_llm") as mock_llm, \
         patch("app.agents.router.get_tool_registry") as mock_registry:

        mock_registry_instance = MagicMock()
        mock_registry_instance.tool_names = ["semantic_search", "kg_search", "keyword_search"]
        mock_registry_instance.tool_descriptions = "- semantic_search: desc\n- kg_search: desc\n- keyword_search: desc"
        mock_registry.return_value = mock_registry_instance

        mock_llm_instance = MagicMock()
        mock_llm_instance.agenerate_structured = AsyncMock(return_value=[
            {"task_id": "t1", "tools": ["semantic_search"]},
            {"task_id": "t2", "tools": ["kg_search", "semantic_search"]},
        ])
        mock_llm.return_value = mock_llm_instance

        state = _make_state([
            {"id": "t1", "description": "find fact", "intent": "fact", "depends_on": [], "status": "pending"},
            {"id": "t2", "description": "find relation", "intent": "relation", "depends_on": [], "status": "pending"},
        ])
        result = await route_node(state)
        assert result["routes"]["t1"] == ["semantic_search"]
        assert result["routes"]["t2"] == ["kg_search", "semantic_search"]


@pytest.mark.asyncio
async def test_router_llm_failure_falls_back_to_rules():
    with patch("app.agents.router.get_llm") as mock_llm, \
         patch("app.agents.router.get_tool_registry") as mock_registry:

        mock_registry_instance = MagicMock()
        mock_registry_instance.tool_names = ["semantic_search", "kg_search", "keyword_search"]
        mock_registry_instance.tool_descriptions = "- semantic_search: desc"
        mock_registry.return_value = mock_registry_instance

        mock_llm_instance = MagicMock()
        mock_llm_instance.agenerate_structured = AsyncMock(side_effect=Exception("LLM dead"))
        mock_llm.return_value = mock_llm_instance

        state = _make_state([
            {"id": "t1", "description": "find fact", "intent": "fact", "depends_on": [], "status": "pending"},
        ])
        result = await route_node(state)
        assert result["routes"]["t1"] == FALLBACK_RULES["fact"]


@pytest.mark.asyncio
async def test_router_filters_invalid_tool_names():
    with patch("app.agents.router.get_llm") as mock_llm, \
         patch("app.agents.router.get_tool_registry") as mock_registry:

        mock_registry_instance = MagicMock()
        mock_registry_instance.tool_names = ["semantic_search"]
        mock_registry_instance.tool_descriptions = "- semantic_search: desc"
        mock_registry.return_value = mock_registry_instance

        mock_llm_instance = MagicMock()
        mock_llm_instance.agenerate_structured = AsyncMock(return_value=[
            {"task_id": "t1", "tools": ["semantic_search", "nonexistent_tool"]},
        ])
        mock_llm.return_value = mock_llm_instance

        state = _make_state([
            {"id": "t1", "description": "find fact", "intent": "fact", "depends_on": [], "status": "pending"},
        ])
        result = await route_node(state)
        assert result["routes"]["t1"] == ["semantic_search"]


@pytest.mark.asyncio
async def test_router_empty_subtasks():
    with patch("app.agents.router.get_tool_registry") as mock_registry:
        mock_registry_instance = MagicMock()
        mock_registry_instance.tool_names = ["semantic_search"]
        mock_registry.return_value = mock_registry_instance

        state = _make_state([])
        result = await route_node(state)
        assert result["routes"] == {}


def test_fallback_rules_cover_all_intents():
    for intent in ["fact", "relation", "exact", "comparison", "reasoning"]:
        assert intent in FALLBACK_RULES
        assert len(FALLBACK_RULES[intent]) > 0