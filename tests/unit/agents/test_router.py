import pytest
from app.agents.state import AgentState
from app.agents.router import route_node


@pytest.mark.asyncio
async def test_router_phase1_all_milvus():
    state: AgentState = {
        "query": "test", "conversation_history": [],
        "intent": "", "rewritten_query": "",
        "sub_tasks": [
            {"id": "t1", "description": "find A", "intent": "fact", "depends_on": [], "status": "pending"},
            {"id": "t2", "description": "find B", "intent": "relation", "depends_on": [], "status": "pending"},
        ],
        "routes": {}, "retrieved": [], "raw_milvus_hits": [], "raw_kg_results": [], "raw_keyword_hits": [],
        "reflection_notes": "", "missing_info": [], "quality_score": 0.0, "need_another_round": False,
        "draft_answer": "", "verified_claims": [], "supplement_queries": [], "need_supplement": False,
        "final_answer": "", "citations": [], "uncertainty_flags": [], "warnings": [], "bare_minimum_mode": False,
        "iteration": 0, "max_iterations": 5, "prev_score": None, "collection_ids": [],
    }
    result = await route_node(state)
    assert result["routes"]["t1"] == "milvus"
    assert result["routes"]["t2"] == "milvus"
