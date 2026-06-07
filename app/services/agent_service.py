import time
from app.agents.state import AgentState
from app.agents.graph import get_graph
from app.core.config import get_settings

settings = get_settings()


def _flatten_routes(routes: dict) -> list[str]:
    flat: set[str] = set()
    for tools in routes.values():
        flat.update(tools)
    return list(flat)


NODE_LABELS = {
    "understand": "Understanding query...",
    "route": "Routing to retrieval paths...",
    "execute": "Executing searches...",
    "reflect": "Reflecting on completeness...",
    "verify": "Verifying claims...",
    "synthesize": "Synthesizing answer...",
    "memory": "Saving to memory...",
}


class AgentService:
    def __init__(self):
        self.graph = get_graph()

    def _build_initial_state(self, query: str, collection_ids: list[str],
                              session_id: str | None, conversation_history: list,
                              opts: dict) -> AgentState:
        return {
            "query": query,
            "conversation_history": conversation_history,
            "intent": "",
            "rewritten_query": "",
            "sub_tasks": [],
            "routes": {},
            "retrieved": [],
            "raw_milvus_hits": [],
            "raw_kg_results": [],
            "raw_keyword_hits": [],
            "reflection_notes": "",
            "missing_info": [],
            "quality_score": 0.0,
            "need_another_round": False,
            "draft_answer": "",
            "verified_claims": [],
            "supplement_queries": [],
            "need_supplement": False,
            "final_answer": "",
            "citations": [],
            "uncertainty_flags": [],
            "warnings": [],
            "bare_minimum_mode": False,
            "iteration": 0,
            "max_iterations": opts.get("max_iterations", settings.max_iterations),
            "prev_score": None,
            "collection_ids": collection_ids,
            "session_id": session_id or "",
            "enable_web_search": opts.get("enable_web_search", False),
        }

    async def _load_conversation(self, session_id: str | None) -> list:
        if not session_id:
            return []
        try:
            from app.core.di import get_redis
            from app.memory.conversation import ConversationMemory
            redis = await get_redis()
            memory = ConversationMemory(redis)
            context = await memory.get_context(session_id)
            return context.get("window", [])
        except Exception:
            return []

    async def _persist_trace(self, db, user_id: str, session_id: str | None,
                              query: str, trace: dict, latency_ms: int) -> None:
        try:
            from app.domain.query_trace import QueryTrace
            from app.domain.base import new_uuid
            trace_row = QueryTrace(
                id=new_uuid(),
                user_id=user_id,
                session_id=session_id,
                query=query,
                answer=trace["answer"],
                model_used=settings.llm_model,
                total_tokens=0,
                estimated_cost=0.0,
                citations=trace["citations"],
                agent_graph={
                    "intent": trace["agent_trace"]["intent"],
                    "iterations": trace["agent_trace"]["iterations"],
                    "quality_score": trace["agent_trace"]["quality_score"],
                    "routes_used": trace["agent_trace"]["routes_used"],
                },
                quality_score=trace["agent_trace"]["quality_score"],
                iterations=trace["agent_trace"]["iterations"],
                latency_ms=latency_ms,
            )
            db.add(trace_row)
            await db.flush()
        except Exception:
            import structlog
            structlog.get_logger().warning("trace_persist_failed", exc_info=True)

    def _build_trace(self, result: dict, latency_ms: int) -> dict:
        return {
            "answer": result.get("final_answer", ""),
            "citations": result.get("citations", []),
            "agent_trace": {
                "intent": result.get("intent"),
                "sub_tasks_executed": len(result.get("sub_tasks", [])),
                "iterations": result.get("iteration", 0),
                "quality_score": result.get("quality_score", 0),
                "routes_used": _flatten_routes(result.get("routes", {})),
            },
            "uncertainty_flags": result.get("uncertainty_flags", []),
        }

    async def run(self, query: str, collection_ids: list[str],
                  db=None, user_id: str | None = None,
                  session_id: str | None = None,
                  options: dict | None = None) -> dict:
        opts = options or {}
        t0 = time.monotonic()

        conversation_history = await self._load_conversation(session_id)
        initial_state = self._build_initial_state(
            query, collection_ids, session_id, conversation_history, opts)
        result = await self.graph.ainvoke(initial_state)
        latency_ms = int((time.monotonic() - t0) * 1000)

        trace = self._build_trace(result, latency_ms)
        await self._persist_trace(db, user_id, session_id, query, trace, latency_ms)
        return trace

    async def run_stream(self, query: str, collection_ids: list[str],
                         session_id: str | None = None,
                         options: dict | None = None):
        """Yield SSE-style dicts as the graph runs each node.

        Each yield is a dict with keys: 'event' (status|chunk|done) and 'data'.
        """
        opts = options or {}
        t0 = time.monotonic()

        conversation_history = await self._load_conversation(session_id)
        initial_state = self._build_initial_state(
            query, collection_ids, session_id, conversation_history, opts)

        seen_nodes: set[str] = set()
        accumulated: dict = {}
        async for event in self.graph.astream(initial_state):
            for node_name, state_update in event.items():
                accumulated.update(state_update)
                label = NODE_LABELS.get(node_name, node_name)
                if node_name not in seen_nodes:
                    seen_nodes.add(node_name)
                    yield {"event": "status", "data": {
                        "phase": node_name, "message": label,
                        "iteration": accumulated.get("iteration", 0)}}

        result = accumulated if accumulated else {}
        latency_ms = int((time.monotonic() - t0) * 1000)
        trace = self._build_trace(result, latency_ms)

        # Emit answer as chunks
        answer = trace["answer"]
        words = answer.split(" ")
        for i in range(0, len(words), 5):
            text = " ".join(words[i:i+5])
            yield {"event": "chunk", "data": {"text": text + " ", "citations": []}}

        yield {"event": "done", "data": {
            "citations": trace["citations"],
            "iterations": trace["agent_trace"]["iterations"],
            "quality_score": trace["agent_trace"]["quality_score"],
        }}
        answer = trace["answer"]
        words = answer.split(" ")
        for i in range(0, len(words), 5):
            text = " ".join(words[i:i+5])
            yield {"event": "chunk", "data": {"text": text + " ", "citations": []}}

        yield {"event": "done", "data": {
            "citations": trace["citations"],
            "iterations": trace["agent_trace"]["iterations"],
            "quality_score": trace["agent_trace"]["quality_score"],
        }}