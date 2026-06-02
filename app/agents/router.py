from app.agents.state import AgentState

# Phase 1: all routes go to milvus (KG/ES not yet available)
# Phase 2 will add: fact->milvus, relation->kg, exact->keyword, comparison->hybrid

async def route_node(state: AgentState) -> AgentState:
    state["routes"] = {}
    for task in state.get("sub_tasks", []):
        state["routes"][task["id"]] = "milvus"
    state["raw_keyword_hits"] = []
    state["raw_kg_results"] = []
    return state
