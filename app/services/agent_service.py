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


class AgentService:
    def __init__(self):
        self.graph = get_graph()

    async def run(self, query: str, collection_ids: list[str],
                  db=None, user_id: str | None = None,
                  session_id: str | None = None,
                  options: dict | None = None) -> dict:
        opts = options or {}
        t0 = time.monotonic()

        # SP2: Load conversation context from Redis
        conversation_history = []
        if session_id:
            try:
                from app.core.di import get_redis
                from app.memory.conversation import ConversationMemory
                redis = await get_redis()
                memory = ConversationMemory(redis)
                context = await memory.get_context(session_id)
                conversation_history = context.get("window", [])
            except Exception:
                pass

        initial_state: AgentState = {
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

        result = await self.graph.ainvoke(initial_state)
        latency_ms = int((time.monotonic() - t0) * 1000)

        trace = {
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

        # SP1: Persist QueryTrace to DB
        if db is not None and user_id is not None:
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

        return trace