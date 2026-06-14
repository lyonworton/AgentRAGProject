import asyncio
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
                              memory_context: dict | None, opts: dict) -> AgentState:
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
            "memory_context": memory_context,
        }

    async def _load_memory_context(self, session_id: str | None, query: str,
                                    user_id: str | None = None) -> tuple[list, dict | None]:
        """Load all memory types and build enriched memory_context with token budget.

        Returns (window_messages, memory_context_dict).
        Priority: summary > topic > facts > window > long-term > KG entities.
        Limit ~2000 chars memory context.
        """
        if not session_id:
            return [], None

        window: list = []
        try:
            from app.core.di import get_redis
            from app.memory.conversation import ConversationMemory
            redis = await get_redis()
            memory = ConversationMemory(redis)
            context = await memory.get_context(session_id)
        except Exception:
            context = {}

        window = context.get("window", [])
        if not context.get("summary") and not context.get("topic") and not context.get("facts") and not window:
            return [], None

        parts: list[str] = []
        budget = 2000

        summary = context.get("summary", "")
        if summary:
            parts.append(f"[Session Summary] {summary[:500]}")
            budget -= min(len(summary), 500)

        topic = context.get("topic", "")
        if topic and budget > 0:
            parts.append(f"[Topic] {topic[:200]}")
            budget -= min(len(topic), 200)

        facts = context.get("facts", [])
        if facts and budget > 0:
            facts_text = "; ".join(facts[:10])
            parts.append(f"[Key Facts] {facts_text[:budget]}")

        ltm_text = await self._search_long_term(query, user_id)
        if ltm_text and budget > 200:
            parts.append(f"[Past Knowledge] {ltm_text[:200]}")
            budget -= min(len(ltm_text), 200)

        kg_entities_text = await self._load_kg_entities(session_id)
        if kg_entities_text and budget > 150:
            parts.append(f"[Known Entities] {kg_entities_text[:150]}")
            budget -= min(len(kg_entities_text), 150)

        memory_text = "\n".join(parts)
        return window, {"text": memory_text} if memory_text else None

    async def _search_long_term(self, query: str, user_id: str | None) -> str:
        """Search LongTermMemoryStore for relevant past knowledge."""
        if not user_id or not query:
            return ""
        try:
            from app.memory.long_term import LongTermMemoryStore
            from app.core.di import get_db
            async for db in get_db():
                store = LongTermMemoryStore(db)
                results = await store.search_by_embedding(query, user_id, top_k=3)
                if results:
                    return " | ".join(
                        r.content.get("text", str(r.content))[:100]
                        for r in results if r.content
                    )
        except Exception:
            pass
        return ""

    async def _load_kg_entities(self, session_id: str) -> str:
        """Load KG entities for session."""
        if not session_id:
            return ""
        try:
            from app.memory.kg_bridge import load_session_entities
            entities = await load_session_entities(session_id)
            if entities:
                return ", ".join(f"{e['name']}({e['type']})" for e in entities[:10])
        except Exception:
            pass
        return ""

    async def _persist_long_term(self, db, user_id: str | None, query: str, answer: str, intent: str) -> None:
        """Fire-and-forget: extract key fact from Q&A and store as long-term memory."""
        if not user_id or not answer:
            return
        try:
            from app.memory.long_term import LongTermMemoryStore
            store = LongTermMemoryStore(db)
            await store.create(
                user_id=user_id,
                type="fact",
                content={"text": answer[:500], "query": query, "intent": intent},
                confidence=0.8,
            )
        except Exception:
            import structlog
            structlog.get_logger().warning("long_term_persist_failed", exc_info=True)

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

        conversation_history, memory_context = await self._load_memory_context(session_id, query, user_id)
        initial_state = self._build_initial_state(
            query, collection_ids, session_id, conversation_history, memory_context, opts)
        result = await self.graph.ainvoke(initial_state)
        latency_ms = int((time.monotonic() - t0) * 1000)

        trace = self._build_trace(result, latency_ms)
        await self._persist_trace(db, user_id, session_id, query, trace, latency_ms)

        if db and user_id:
            intent = result.get("intent", "")
            await self._persist_long_term(db, user_id, query, trace["answer"], intent)

        return trace

    async def run_stream(self, query: str, collection_ids: list[str],
                         session_id: str | None = None,
                         options: dict | None = None):
        """Yield SSE-style dicts as the graph runs each node.

        Each yield is a dict with keys: 'event' (status|thought|chunk|done|timeout) and 'data'.

        Events:
          - status: phase change (e.g. "Understanding query...")
          - thought: internal reasoning output (draft, reflection, claims)
          - chunk: answer text fragment
          - done: final result with citations
          - timeout: 45s timeout reached, partial result
        """
        opts = options or {}
        t0 = time.monotonic()
        timeout = opts.get("timeout", 180)

        conversation_history, memory_context = await self._load_memory_context(session_id, query)
        initial_state = self._build_initial_state(
            query, collection_ids, session_id, conversation_history, memory_context, opts)

        seen_nodes: set[str] = set()
        accumulated: dict = {}
        last_thoughts: dict[str, str] = {}  # node_name -> last value, for dedup

        async def _stream_graph():
            async for event in self.graph.astream(initial_state):
                for node_name, state_update in event.items():
                    accumulated.update(state_update)
                    label = NODE_LABELS.get(node_name, node_name)
                    if node_name not in seen_nodes:
                        seen_nodes.add(node_name)
                        yield {"event": "status", "data": {
                            "phase": node_name, "message": label,
                            "iteration": accumulated.get("iteration", 0)}}

                    # Yield thought events for key reasoning nodes
                    thought = None
                    if node_name == "reflect":
                        draft = accumulated.get("draft_answer", "")
                        notes = accumulated.get("reflection_notes", "")
                        if draft and draft != last_thoughts.get("draft"):
                            last_thoughts["draft"] = draft
                            thought = {"phase": "Draft", "text": draft[:500]}
                        elif notes and notes != last_thoughts.get("reflect"):
                            last_thoughts["reflect"] = notes
                            score = accumulated.get("quality_score", 0)
                            thought = {"phase": "Reflection", "text": notes[:500],
                                       "score": score}
                    elif node_name == "verify":
                        claims = accumulated.get("verified_claims", [])
                        if claims:
                            key = str(len(claims))
                            if key != last_thoughts.get("verify"):
                                last_thoughts["verify"] = key
                                verified = sum(1 for c in claims if c.get("status") == "verified")
                                thought = {"phase": "Verification",
                                           "text": f"{verified}/{len(claims)} claims verified",
                                           "claims": claims[:5]}
                    elif node_name == "understand":
                        intent = accumulated.get("intent", "")
                        rewritten = accumulated.get("rewritten_query", "")
                        if intent and intent != last_thoughts.get("intent"):
                            last_thoughts["intent"] = intent
                            subtasks = len(accumulated.get("sub_tasks", []))
                            thought = {"phase": "Analysis",
                                       "text": f"Intent: {intent} | Rewritten: {rewritten[:100]} | {subtasks} subtasks"}

                    if thought:
                        yield {"event": "thought", "data": thought}

        try:
            async for msg in _stream_graph():
                yield msg
        except asyncio.TimeoutError:
            pass  # fall through to partial result
        except Exception:
            import structlog
            structlog.get_logger().warning("graph_stream_error", exc_info=True)

        result = accumulated if accumulated else {}
        latency_ms = int((time.monotonic() - t0) * 1000)
        trace = self._build_trace(result, latency_ms)

        # If no final_answer, use draft or synthesize from retrieved
        answer = trace["answer"]
        if not answer:
            draft = result.get("draft_answer", "")
            if draft:
                answer = draft
                trace["answer"] = draft
            else:
                answer = "I couldn't find enough information to answer this question."
                trace["answer"] = answer

        # Chunks first — stream answer word groups
        words = answer.split(" ")
        for i in range(0, len(words), 5):
            text = " ".join(words[i:i+5])
            yield {"event": "chunk", "data": {"text": text + " ", "citations": []}}

        # Done last — includes answer for session persistence
        timed_out = latency_ms > timeout * 1000
        yield {"event": "done", "data": {
            "answer": answer,
            "citations": trace["citations"],
            "iterations": trace["agent_trace"]["iterations"],
            "quality_score": trace["agent_trace"]["quality_score"],
            "timed_out": timed_out,
            "latency_ms": latency_ms,
        }}