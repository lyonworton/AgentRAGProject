import structlog
from langgraph.graph import StateGraph, END, START
from app.agents.state import AgentState
from app.agents.understander import understand_node
from app.agents.router import route_node
from app.agents.executor import executor_node
from app.agents.reflector import reflector_node
from app.agents.verifier import verifier_node
from app.agents.nodes import synthesize_node

logger = structlog.get_logger()

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
        # Phase 7: Progressive summarization — merge with previous summary
        old_context = {}
        try:
            old_context = await memory.get_context(session_id)
        except Exception:
            pass
        old_summary = old_context.get("summary", "") if old_context else ""
        from app.memory.summarizer import progressive_summarize
        summary = await progressive_summarize(old_summary, query, answer)
        await memory.save_summary(session_id, summary)

        # Phase 7 SP3: Extract entities → Neo4j UserMemory (fire-and-forget)
        if session_id and session_id != 'default':
            try:
                from app.memory.kg_bridge import extract_entities, save_session_entities
                entities = await extract_entities(query, answer)
                if entities:
                    await save_session_entities(session_id, entities)
            except Exception:
                import structlog
                structlog.get_logger().warning('kg_entity_persist_failed', exc_info=True)
    except Exception:
        import structlog
        structlog.get_logger().warning('memory_node_persist_failed', exc_info=True)
    return state


async def should_continue(state: AgentState) -> str:
    logger.info("should_continue", iteration=state["iteration"], max_iterations=state["max_iterations"],
                quality_score=state["quality_score"], sub_tasks=len(state.get("sub_tasks", [])),
                retrieved=len(state.get("retrieved", [])), prev_score=state.get("prev_score"),
                intent=state.get("intent", ""))
    if state["iteration"] >= state["max_iterations"]:
        # Even at max iterations, run verification if quality is good enough
        if state["quality_score"] >= 0.7:
            return "verify"
        logger.info("should_continue: max_iterations_reached")
        return "synthesize"
    # No improvement: retrieved chunk IDs unchanged from last round → stop looping
    retrieved_ids = {r.get("chunk_id") for r in state.get("retrieved", [])}
    prev_retrieved_ids = set(state.get("_prev_retrieved_ids", []))
    if prev_retrieved_ids and retrieved_ids == prev_retrieved_ids:
        return "synthesize"
    # Empty results after execution → no point looping
    retrieved = state.get("retrieved")
    if retrieved is not None and not retrieved:
        return "synthesize"
    # 已查到足够多 chunks 但 quality 仍低 → 大概率是缺角度而非缺内容，不再循环
    if len(retrieved) >= 40 and state["iteration"] >= 1:
        return "synthesize"
    # Note: iteration is incremented in reflector_node, not here.
    # should_continue is a conditional-edge function — its state mutations
    # are NOT persisted by LangGraph checkpointing.
    # Always run verifier when score >= 0.7 to show verification process
    if state["quality_score"] >= 0.7:
        return "verify"
    if state.get("prev_score") is not None and state["quality_score"] <= state["prev_score"]:
        return "verify"
    return "route"


async def should_verify(state: AgentState) -> str:
    if state.get("need_supplement"):
        # If reflect already rated quality high enough, skip supplemental search
        if state.get("quality_score", 0) >= 0.9:
            logger.info("should_verify: skipping supplement, quality_sufficient",
                        quality_score=state["quality_score"])
            return "synthesize"
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

    logger.info("graph_built", nodes=graph.nodes.keys() if hasattr(graph, 'nodes') else "compiled")

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
