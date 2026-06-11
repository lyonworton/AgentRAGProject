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
            {"task_id": "t1", "extra_tools": []},
            {"task_id": "t2", "extra_tools": ["semantic_search"]},
        ])
        mock_llm.return_value = mock_llm_instance

        state = _make_state([
            {"id": "t1", "description": "find fact", "intent": "fact", "depends_on": [], "status": "pending"},
            {"id": "t2", "description": "find relation", "intent": "relation", "depends_on": [], "status": "pending"},
        ])
        # No route_suggestions → falls back to LLM
        result = await route_node(state)
        assert result["routes"]["t1"] == ["semantic_search"]
        assert result["routes"]["t2"] == ["kg_search", "semantic_search"]


@pytest.mark.asyncio
async def test_router_uses_precomputed_route_suggestions():
    """When understander provides route_suggestions, router uses them instead of LLM."""
    with patch("app.agents.router.get_llm") as mock_llm, \
         patch("app.agents.router.get_tool_registry") as mock_registry:

        mock_registry_instance = MagicMock()
        mock_registry_instance.tool_names = ["semantic_search", "kg_search", "keyword_search"]
        mock_registry_instance.tool_descriptions = ""
        mock_registry.return_value = mock_registry_instance

        # LLM should NOT be called
        mock_llm_instance = MagicMock()
        mock_llm.return_value = mock_llm_instance

        state = _make_state([
            {"id": "t1", "description": "find fact", "intent": "fact", "depends_on": [], "status": "pending"},
            {"id": "t2", "description": "find relation", "intent": "relation", "depends_on": [], "status": "pending"},
        ])
        state["route_suggestions"] = [
            {"task_id": "t1", "extra_tools": ["kg_search"]},
            {"task_id": "t2", "extra_tools": ["semantic_search"]},
        ]
        result = await route_node(state)
        # LLM was not called
        mock_llm_instance.agenerate_structured.assert_not_called()
        # Baseline + suggestions applied
        assert "semantic_search" in result["routes"]["t1"]
        assert "kg_search" in result["routes"]["t1"]
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
            {"task_id": "t1", "extra_tools": ["nonexistent_tool"]},
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


def test_apply_rules_baseline():
    from app.agents.router import _apply_rules_baseline
    tasks = [
        {"id": "t1", "intent": "fact"},
        {"id": "t2", "intent": "exact"},
        {"id": "t3", "intent": "relation"},
        {"id": "t4", "intent": "unknown_intent"},
    ]
    result = _apply_rules_baseline(tasks, FALLBACK_RULES)
    assert result["t1"] == ["semantic_search"]
    assert result["t2"] == ["keyword_search"]
    assert result["t3"] == ["kg_search"]
    assert result["t4"] == ["semantic_search"]


@pytest.mark.asyncio
async def test_router_exact_intent_routes_to_keyword_search():
    """exact intent → keyword_search always via baseline, even if LLM fails."""
    with patch("app.agents.router.get_llm") as mock_llm, \
         patch("app.agents.router.get_tool_registry") as mock_registry:

        mock_registry_instance = MagicMock()
        mock_registry_instance.tool_names = ["semantic_search", "kg_search", "keyword_search"]
        mock_registry_instance.tool_descriptions = "- keyword_search: desc"
        mock_registry.return_value = mock_registry_instance

        # LLM fails — baseline must ensure keyword_search is still used
        mock_llm_instance = MagicMock()
        mock_llm_instance.agenerate_structured = AsyncMock(side_effect=Exception("LLM dead"))
        mock_llm.return_value = mock_llm_instance

        state = _make_state([
            {"id": "t1", "description": "find doc DOC-12345", "intent": "exact", "depends_on": [], "status": "pending"},
        ])
        result = await route_node(state)
        assert "keyword_search" in result["routes"]["t1"]


@pytest.mark.asyncio
async def test_router_llm_enhances_does_not_replace():
    """LLM suggests extra tools, baseline tools are still present."""
    with patch("app.agents.router.get_llm") as mock_llm, \
         patch("app.agents.router.get_tool_registry") as mock_registry:

        mock_registry_instance = MagicMock()
        mock_registry_instance.tool_names = ["semantic_search", "kg_search", "keyword_search"]
        mock_registry_instance.tool_descriptions = "- semantic_search: desc\n- kg_search: desc"
        mock_registry.return_value = mock_registry_instance

        mock_llm_instance = MagicMock()
        mock_llm_instance.agenerate_structured = AsyncMock(return_value=[
            {"task_id": "t1", "extra_tools": ["kg_search", "keyword_search"]},
        ])
        mock_llm.return_value = mock_llm_instance

        state = _make_state([
            {"id": "t1", "description": "find fact about entities", "intent": "fact", "depends_on": [], "status": "pending"},
        ])
        result = await route_node(state)
        # Baseline semantic_search still present
        assert "semantic_search" in result["routes"]["t1"]
        # LLM extras added
        assert "kg_search" in result["routes"]["t1"]
        assert "keyword_search" in result["routes"]["t1"]


@pytest.mark.asyncio
async def test_router_llm_suggests_already_present_tool_not_duplicated():
    """LLM suggesting a tool already in baseline should not duplicate it."""
    with patch("app.agents.router.get_llm") as mock_llm, \
         patch("app.agents.router.get_tool_registry") as mock_registry:

        mock_registry_instance = MagicMock()
        mock_registry_instance.tool_names = ["semantic_search", "kg_search", "keyword_search"]
        mock_registry_instance.tool_descriptions = "- semantic_search: desc\n- kg_search: desc"
        mock_registry.return_value = mock_registry_instance

        mock_llm_instance = MagicMock()
        # LLM also suggests semantic_search, which is already in baseline
        mock_llm_instance.agenerate_structured = AsyncMock(return_value=[
            {"task_id": "t1", "extra_tools": ["semantic_search", "kg_search"]},
        ])
        mock_llm.return_value = mock_llm_instance

        state = _make_state([
            {"id": "t1", "description": "find fact", "intent": "fact", "depends_on": [], "status": "pending"},
        ])
        result = await route_node(state)
        # semantic_search appears exactly once
        assert result["routes"]["t1"].count("semantic_search") == 1
        assert "kg_search" in result["routes"]["t1"]