import json
from app.agents.state import AgentState
from app.core.llm_factory import get_llm

UNDERSTAND_PROMPT = """Analyze the user's query and conversation history. You are a query understanding specialist.

Your tasks:
1. Determine the intent: "fact" (simple lookup), "relation" (entity relationships), "comparison" (comparing things), "reasoning" (complex analysis)
2. Rewrite the query to be more specific and search-friendly
3. Decompose the query into sub-tasks. Each sub-task should be independently retrievable.
4. Mark dependencies: if sub-task B needs results from sub-task A first, list A's id in B's depends_on

Output ONLY valid JSON, no explanation:
{
  "intent": "fact|relation|comparison|reasoning",
  "rewritten_query": "...",
  "sub_tasks": [
    {"id": "t1", "description": "...", "intent": "fact", "depends_on": []},
    {"id": "t2", "description": "...", "intent": "relation", "depends_on": ["t1"]}
  ]
}
"""


async def understand_node(state: AgentState) -> AgentState:
    llm = get_llm()
    prompt = f"{UNDERSTAND_PROMPT}\n\nQuery: {state['query']}\nHistory: {json.dumps(state.get('conversation_history', []))}"
    result = await llm.agenerate_structured(prompt, "You are a query analysis expert.", {
        "type": "object", "properties": {
            "intent": {"type": "string", "enum": ["fact", "relation", "comparison", "reasoning"]},
            "rewritten_query": {"type": "string"},
            "sub_tasks": {"type": "array", "items": {"type": "object", "properties": {
                "id": {"type": "string"}, "description": {"type": "string"},
                "intent": {"type": "string"}, "depends_on": {"type": "array", "items": {"type": "string"}}
            }, "required": ["id", "description", "intent", "depends_on"]}}
        }, "required": ["intent", "rewritten_query", "sub_tasks"]
    })

    state["intent"] = result["intent"]
    state["rewritten_query"] = result["rewritten_query"]
    state["sub_tasks"] = [
        {"id": t["id"], "description": t["description"], "intent": t["intent"],
         "depends_on": t.get("depends_on", []), "status": "pending"}
        for t in result["sub_tasks"]
    ]
    return state
