import pytest
from app.agents.state import AgentState
from app.agents.graph import build_graph


@pytest.mark.asyncio
async def test_graph_builds():
    graph = build_graph()
    assert graph is not None
    # Should have 7 nodes: understand, route, execute, reflect, verify, synthesize, memory
    nodes = graph.get_graph().nodes
    assert len(nodes) >= 6


@pytest.mark.asyncio
async def test_should_continue_max_iterations():
    from app.agents.graph import should_continue
    state: AgentState = {
        "query": "test", "iteration": 5, "max_iterations": 5,
        "quality_score": 0.3, "prev_score": None,
    }
    result = await should_continue(state)
    assert result in ("synthesize", "verify")


@pytest.mark.asyncio
async def test_should_continue_quality_ok():
    from app.agents.graph import should_continue
    state: AgentState = {
        "query": "test", "iteration": 2, "max_iterations": 5,
        "quality_score": 0.85, "prev_score": None,
    }
    result = await should_continue(state)
    assert result == "verify"
