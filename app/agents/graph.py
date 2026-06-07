from langgraph.graph import StateGraph, END, START
from app.agents.state import AgentState
from app.agents.understander import understand_node
from app.agents.router import route_node
from app.agents.executor import executor_node
from app.agents.reflector import reflector_node
from app.agents.verifier import verifier_node
from app.agents.nodes import synthesize_node

async def memory_node(state: AgentState) -> AgentState:
    """Persist conversation context to Redis short-term memory."""
    if not state.get('final_answer'):
        return state
    try:
        from app.core.di import get_redis
        from app.memory.conversation import ConversationMemory
        redis = await get_redis()
        memory = ConversationMemory(redis)
        session_id = state.get('session_id', 'default')
        query = state.get('query', '')
        answer = state.get('final_answer', '')
        intent = state.get('intent', '')
        if intent:
            await memory.save_topic(session_id, intent)
        citations = state.get('citations', [])
        if citations:
            facts = [f"[{c.get('chunk_id','?')}] {c.get('text','')[:200]}" for c in citations[:5]]
            await memory.save_facts(session_id, facts)
        window_entry = [{'role': 'user', 'content': query}, {'role': 'assistant', 'content': answer[:1000]}]
        existing = await memory.aload(f'session:{session_id}:window')
        existing_msgs = (existing or {}).get('messages', [])
        existing_msgs.extend(window_entry)
        await memory.save_window(session_id, existing_msgs)
        summary = answer[:500] if len(answer) > 500 else answer
        await memory.save_summary(session_id, summary)
    except Exception:
        import structlog
        structlog.get_logger().warning('memory_node_persist_failed', exc_info=True)
    return state


async def should_continue(state: AgentState) -> str:
    if state["iteration"] >= state["max_iterations"]:
        return "synthesize"
    if state["quality_score"] >= 0.7:
        return "verify"
    if state.get("prev_score") and state["quality_score"] <= state["prev_score"]:
        return "verify"
    state["iteration"] += 1
    state["prev_score"] = state["quality_score"]
    return "route"


async def should_verify(state: AgentState) -> str:
    if state.get("need_supplement"):
        return "route"
    return "synthesize"


def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("understand", understand_node)
    graph.add_node("route", route_node)
    graph.add_node("execute", executor_node)
    graph.add_node("reflect", reflector_node)
    graph.add_node("verify", verifier_node)
    graph.add_node("synthesize", synthesize_node)
    graph.add_node("memory", memory_node)

    graph.add_edge(START, "understand")
    graph.add_edge("understand", "route")
    graph.add_edge("route", "execute")
    graph.add_edge("execute", "reflect")

    graph.add_conditional_edges("reflect", should_continue, {
        "route": "route",
        "verify": "verify",
        "synthesize": "synthesize",
    })

    graph.add_conditional_edges("verify", should_verify, {
        "route": "route",
        "synthesize": "synthesize",
    })

    graph.add_edge("synthesize", "memory")
    graph.add_edge("memory", END)

    return graph.compile()


_graph_instance = None

def get_graph():
    global _graph_instance
    if _graph_instance is None:
        _graph_instance = build_graph()
    return _graph_instance
