import json
import structlog
from app.agents.state import AgentState
from app.core.llm_factory import get_llm

logger = structlog.get_logger()

UNDERSTAND_PROMPT = """Analyze the user's query, conversation history, and session memory context. You are a query understanding specialist.

Your tasks:
1. Determine the intent: "fact" (simple lookup), "relation" (entity relationships), "comparison" (comparing things), "reasoning" (complex analysis), "exact" (exact match, ID lookup, quoted phrase, code search)
2. Rewrite the query to be more specific and search-friendly
3. Decompose the query into sub-tasks. Each sub-task should be independently retrievable.
4. Mark dependencies: if sub-task B needs results from sub-task A first, list A's id in B's depends_on
5. Use the memory context to disambiguate pronouns, resolve entities, and maintain topic continuity.
6. For each sub-task, suggest ADDITIONAL retrieval tools beyond the baseline. Available tools: semantic_search, kg_search, keyword_search. Guidelines:
   - "fact" baseline is semantic_search; consider kg_search for entity-heavy facts
   - "relation" baseline is kg_search; consider semantic_search for context
   - "exact" baseline is keyword_search; consider semantic_search for recall
   - "comparison" baseline is semantic_search + kg_search
   - "reasoning" baseline is all three; leave extra_tools empty

Output ONLY valid JSON, no explanation:
{
  "intent": "fact|relation|comparison|reasoning|exact",
  "rewritten_query": "...",
  "sub_tasks": [
    {"id": "t1", "description": "...", "intent": "fact", "depends_on": []},
    {"id": "t2", "description": "...", "intent": "relation", "depends_on": ["t1"]}
  ],
  "route_suggestions": [
    {"task_id": "t1", "extra_tools": ["kg_search"]}
  ]
}
"""


async def understand_node(state: AgentState) -> AgentState:
    llm = get_llm()
    mc = state.get("memory_context") or {}
    memory_text = mc.get("text", "")
    memory_block = f"\n\nMemory Context:\n{memory_text}" if memory_text else ""
    prompt = (
        f"{UNDERSTAND_PROMPT}"
        f"\n\nQuery: {state['query']}"
        f"\nHistory: {json.dumps(state.get('conversation_history', []))}"
        f"{memory_block}"
    )
    logger.info("understand_node_start", query=state.get("query", "")[:100], memory_context=bool(mc))
    result = await llm.agenerate_structured(prompt, "You are a query analysis expert.", {
        "type": "object", "properties": {
            "intent": {"type": "string", "enum": ["fact", "relation", "comparison", "reasoning", "exact"]},
            "rewritten_query": {"type": "string"},
            "sub_tasks": {"type": "array", "items": {"type": "object", "properties": {
                "id": {"type": "string"}, "description": {"type": "string"},
                "intent": {"type": "string"}, "depends_on": {"type": "array", "items": {"type": "string"}}
            }, "required": ["id", "description", "intent", "depends_on"]}},
            "route_suggestions": {"type": "array", "items": {"type": "object", "properties": {
                "task_id": {"type": "string"}, "extra_tools": {"type": "array", "items": {"type": "string"}}
            }, "required": ["task_id", "extra_tools"]}}
        }, "required": ["intent", "rewritten_query", "sub_tasks"]
    })

    state["intent"] = result["intent"]
    state["rewritten_query"] = result["rewritten_query"]
    state["sub_tasks"] = [
        {"id": t["id"], "description": t["description"], "intent": t["intent"],
         "depends_on": t.get("depends_on", []), "status": "pending"}
        for t in result["sub_tasks"]
    ]
    state["route_suggestions"] = result.get("route_suggestions", [])
    logger.info("understand_node_done", intent=state["intent"], sub_tasks=len(state["sub_tasks"]))
    return state
