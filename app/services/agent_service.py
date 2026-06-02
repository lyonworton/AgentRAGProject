from app.agents.state import AgentState
from app.agents.graph import get_graph
from app.core.config import get_settings

settings = get_settings()


class AgentService:
    def __init__(self):
        self.graph = get_graph()

    async def run(self, query: str, collection_ids: list[str], session_id: str | None = None,
                  options: dict | None = None) -> dict:
        opts = options or {}
        initial_state: AgentState = {
            "query": query,
            "conversation_history": [],
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
        }

        result = await self.graph.ainvoke(initial_state)
        return {
            "answer": result.get("final_answer", ""),
            "citations": result.get("citations", []),
            "agent_trace": {
                "intent": result.get("intent"),
                "sub_tasks_executed": len(result.get("sub_tasks", [])),
                "iterations": result.get("iteration", 0),
                "quality_score": result.get("quality_score", 0),
                "routes_used": list(set(result.get("routes", {}).values())),
            },
            "uncertainty_flags": result.get("uncertainty_flags", []),
        }
